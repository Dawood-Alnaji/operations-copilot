"""
API Views for Knowledge Base
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse

from knowledge_base.models import Document, KnowledgeQuery
from knowledge_base.services import RAGService
from knowledge_base.serializers import (
    DocumentSerializer, DocumentUploadSerializer,
    KnowledgeQueryRequestSerializer, KnowledgeQueryResponseSerializer,
    KnowledgeQueryHistorySerializer
)
from audit.models import AuditLog

logger = logging.getLogger(__name__)


class DocumentUploadView(APIView):
    """Upload documents to knowledge base (Admin only)"""
    
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    @extend_schema(
        request=DocumentUploadSerializer,
        responses={
            201: DocumentSerializer,
            400: OpenApiResponse(description="Invalid file or duplicate"),
            403: OpenApiResponse(description="Insufficient permissions"),
        },
        description="Upload PDF or DOCX document to knowledge base. Admin only."
    )
    def post(self, request):
        # Check admin permission
        if not hasattr(request.user, 'profile') or not request.user.profile.has_document_upload_permission():
            return Response(
                {'error': 'Only administrators can upload documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            rag_service = RAGService()
            document, upload_status = rag_service.upload_document(
                file=serializer.validated_data['file'],
                title=serializer.validated_data['title'],
                user=request.user,
                metadata=serializer.validated_data.get('metadata')
            )
            
            if upload_status == 'duplicate':
                return Response(
                    {
                        'message': 'Document already exists',
                        'document': DocumentSerializer(document).data
                    },
                    status=status.HTTP_200_OK
                )
            
            # Trigger processing (could be async with Celery in production)
            rag_service.process_document(document.id)
            
            return Response(
                DocumentSerializer(document).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            logger.error(f"Document upload failed: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DocumentListView(ListAPIView):
    """List uploaded documents"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer
    queryset = Document.objects.all().order_by('-upload_timestamp')
    
    @extend_schema(
        description="List all uploaded documents in the knowledge base"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class DocumentDeleteView(APIView):
    """Delete document from knowledge base (Admin only)"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        responses={
            204: OpenApiResponse(description="Document deleted successfully"),
            403: OpenApiResponse(description="Insufficient permissions"),
            404: OpenApiResponse(description="Document not found"),
        },
        description="Delete document. Admin only."
    )
    def delete(self, request, document_id):
        # Check admin permission
        if not hasattr(request.user, 'profile') or not request.user.profile.has_document_upload_permission():
            return Response(
                {'error': 'Only administrators can delete documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            document = Document.objects.get(id=document_id)
            
            # Log deletion
            AuditLog.log_action(
                user=request.user,
                action_type='document_delete',
                resource_type='document',
                resource_id=document_id,
                request_payload={'title': document.title},
                success=True
            )
            
            document.delete()
            
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        except Document.DoesNotExist:
            return Response(
                {'error': 'Document not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class KnowledgeQueryView(APIView):
    """Query knowledge base with RAG"""
    
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        request=KnowledgeQueryRequestSerializer,
        responses={
            200: KnowledgeQueryResponseSerializer,
            400: OpenApiResponse(description="Invalid query"),
            500: OpenApiResponse(description="Query processing failed"),
        },
        description="Query the knowledge base using natural language. Returns answer with source citations."
    )
    def post(self, request):
        serializer = KnowledgeQueryRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            from core.flows.knowledge_retrieval_flow.flow import KnowledgeRetrievalFlow
            flow = KnowledgeRetrievalFlow()
            answer = flow.kickoff(user_query=serializer.validated_data['query'])
            
            result = {
                'answer': answer,
                'sources': [], # Sources are handled by the tool internally now
                'confidence': 0.9
            }
            
            response_serializer = KnowledgeQueryResponseSerializer(data=result)
            response_serializer.is_valid(raise_exception=True)
            
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Knowledge query failed: {e}")
            return Response(
                {'error': 'Query processing failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class KnowledgeQueryHistoryView(ListAPIView):
    """View query history"""
    
    permission_classes = [IsAuthenticated]
    serializer_class = KnowledgeQueryHistorySerializer
    
    def get_queryset(self):
        # Users see their own queries, managers/admins see all
        if hasattr(self.request.user, 'profile') and self.request.user.profile.has_analytics_access():
            return KnowledgeQuery.objects.all().order_by('-timestamp')
        else:
            return KnowledgeQuery.objects.filter(user=self.request.user).order_by('-timestamp')
    
    @extend_schema(
        description="View query history. Users see their own, managers/admins see all."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
