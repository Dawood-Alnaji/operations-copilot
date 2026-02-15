"""
API Views for Field Operations
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiResponse

from field_operations.models import FieldInspection, InspectionAnalysis
from field_operations.services import ImageAnalysisService, AgentOrchestrator
from field_operations.serializers import (
    FieldInspectionSerializer, InspectionUploadSerializer,
    InspectionAnalysisSerializer, InspectionDetailSerializer
)
from audit.models import AuditLog

logger = logging.getLogger(__name__)


class InspectionUploadView(APIView):
    """Upload field inspection images"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        request=InspectionUploadSerializer,
        responses={
            201: InspectionAnalysisSerializer,
            400: OpenApiResponse(description="Invalid data"),
        },
        description="Upload field inspection image for equipment analysis"
    )
    def post(self, request):
        serializer = InspectionUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Create inspection record
            inspection = FieldInspection.objects.create(
                inspector=request.user,
                image=serializer.validated_data['image'],
                equipment_type=serializer.validated_data['equipment_type'],
                location=serializer.validated_data.get('location', ''),
                notes=serializer.validated_data.get('notes', ''),
                analysis_requested=serializer.validated_data.get('analyze_immediately', True)
            )
            
            # Log upload
            AuditLog.log_action(
                user=request.user,
                action_type='inspection_upload',
                resource_type='inspection',
                resource_id=inspection.id,
                request_payload={'equipment_type': inspection.equipment_type},
                success=True
            )
            
            # Analyze if requested
            if serializer.validated_data.get('analyze_immediately', True):
                analysis_service = ImageAnalysisService()
                analysis_result = analysis_service.analyze_field_image(
                    inspection_id=inspection.id,
                    user=request.user
                )
                
                # If high risk or emergency, trigger multi-agent analysis
                if analysis_result.get('is_emergency') or analysis_result.get('risk_classification') in ['high', 'critical']:
                    orchestrator = AgentOrchestrator()
                    inspection_analysis = InspectionAnalysis.objects.get(inspection=inspection)
                    orchestrator.orchestrate_analysis(inspection_analysis.id)
                
                return Response(analysis_result, status=status.HTTP_201_CREATED)
            else:
                return Response(
                    FieldInspectionSerializer(inspection).data,
                    status=status.HTTP_201_CREATED
                )
        
        except Exception as e:
            logger.error(f"Inspection upload failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InspectionListView(ListAPIView):
    """List inspections"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = FieldInspectionSerializer
    
    def get_queryset(self):
        # Users see their own inspections, managers/admins see all
        if hasattr(self.request.user, 'profile') and self.request.user.profile.has_analytics_access():
            return FieldInspection.objects.all().order_by('-upload_timestamp')
        else:
            return FieldInspection.objects.filter(inspector=self.request.user).order_by('-upload_timestamp')
    
    @extend_schema(
        description="List field inspections. Users see their own, managers/admins see all."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class InspectionDetailView(RetrieveAPIView):
    """Get detailed inspection analysis"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = InspectionDetailSerializer
    lookup_field = 'inspection_id'
    
    def get_queryset(self):
        # Users see their own, managers/admins see all
        if hasattr(self.request.user, 'profile') and self.request.user.profile.has_analytics_access():
            return InspectionAnalysis.objects.prefetch_related('agent_logs').all()
        else:
            return InspectionAnalysis.objects.filter(
                inspection__inspector=self.request.user
            ).prefetch_related('agent_logs')
    
    @extend_schema(
        description="Get detailed inspection analysis including multi-agent reasoning"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AnalyticsRiskSummaryView(APIView):
    """Risk analytics dashboard data (Manager/Admin only)"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            200: OpenApiResponse(description="Risk summary statistics"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        description="Get risk analytics summary. Manager/Admin only."
    )
    def get(self, request):
        # Check permissions
        if not hasattr(request.user, 'profile') or not request.user.profile.has_analytics_access():
            return Response(
                {'error': 'Insufficient permissions'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from django.db.models import Count, Q
            from datetime.datetime import timedelta
            from django.utils import timezone
            
            # Risk distribution
            risk_distribution = InspectionAnalysis.objects.values('risk_classification').annotate(
                count=Count('id')
            )
            
            # Emergency count (last 30 days)
            thirty_days_ago = timezone.now() - timedelta(days=30)
            emergency_count = InspectionAnalysis.objects.filter(
                is_emergency=True,
                analysis_timestamp__gte=thirty_days_ago
            ).count()
            
            # Equipment type breakdown
            equipment_breakdown = InspectionAnalysis.objects.select_related('inspection').values(
                'inspection__equipment_type'
            ).annotate(count=Count('id'))
            
            # Total inspections
            total_inspections = FieldInspection.objects.count()
            
            return Response({
                'risk_distribution': list(risk_distribution),
                'emergency_count_30_days': emergency_count,
                'equipment_breakdown': list(equipment_breakdown),
                'total_inspections': total_inspections,
                'generated_at': timezone.now().isoformat()
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Analytics query failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class EmergencyAlertsView(ListAPIView):
    """List recent emergency alerts (Manager/Admin only)"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = InspectionAnalysisSerializer
    
    def get_queryset(self):
        # Check permissions
        if not hasattr(self.request.user, 'profile') or not self.request.user.profile.has_analytics_access():
            return InspectionAnalysis.objects.none()
        
        return InspectionAnalysis.objects.filter(
            is_emergency=True
        ).order_by('-analysis_timestamp')[:50]
    
    @extend_schema(
        description="List recent emergency alerts. Manager/Admin only."
    )
    def get(self, request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.has_analytics_access():
            return Response(
                {'error': 'Insufficient permissions'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().get(request, *args, **kwargs)
