"""
Image Analysis Service for Field Operations

Handles multimodal vision LLM integration for equipment inspection,
risk classification, and emergency detection.
"""

import logging
import json
import re
from typing import Dict, Any, Optional
import time

from django.conf import settings
from django.db import transaction

from field_operations.models import FieldInspection, InspectionAnalysis
from core.tools import vision_llm
from audit.models import AuditLog

logger = logging.getLogger(__name__)


class ImageAnalysisService:
    """Service for vision-based field inspection analysis"""
    
    # Emergency keywords for detection
    EMERGENCY_KEYWORDS = [
        'fire', 'explosion', 'smoke', 'flames', 'burning',
        'electrocution', 'electric shock', 'severe damage',
        'transformer failure', 'critical failure', 'imminent danger',
        'overheating critical', 'arcing', 'sparking excessive'
    ]
    
    def analyze_field_image(
        self, 
        inspection_id: int, 
        user
    ) -> Dict[str, Any]:
        """
        Analyze field inspection image using vision LLM
        
        Args:
            inspection_id: ID of FieldInspection to analyze
            user: User requesting analysis
        
        Returns:
            Dict with analysis results
        """
        start_time = time.time()
        
        try:
            inspection = FieldInspection.objects.select_related('inspector').get(id=inspection_id)
            
            # Check if already analyzed
            if hasattr(inspection, 'analysis'):
                logger.info(f"Inspection {inspection_id} already has analysis")
                return self._format_analysis_response(inspection.analysis)
            
            # Prepare vision prompt
            prompt = self._generate_vision_prompt(inspection.equipment_type, inspection.notes)
            
            # Call vision LLM
            logger.info(f"Calling vision LLM for inspection {inspection_id}")
            llm_output = self._call_vision_llm(inspection.image.path, prompt)
            
            # Parse structured output
            parsed_output = self._parse_llm_output(llm_output)
            
            # Detect emergency
            is_emergency = self._detect_emergency(parsed_output)
            
            # Save analysis
            analysis = self._save_analysis(
                inspection=inspection,
                parsed_output=parsed_output,
                is_emergency=is_emergency,
                raw_output=llm_output
            )
            
            # Log to audit trail
            execution_time_ms = int((time.time() - start_time) * 1000)
            AuditLog.log_action(
                user=user,
                action_type='inspection_analysis',
                resource_type='inspection',
                resource_id=inspection_id,
                request_payload={'equipment_type': inspection.equipment_type},
                response_summary={
                    'risk_level': analysis.risk_classification,
                    'is_emergency': is_emergency,
                    'execution_time_ms': execution_time_ms
                },
                success=True
            )
            
            logger.info(f"Analysis completed for inspection {inspection_id}")
            return self._format_analysis_response(analysis)
        
        except Exception as e:
            logger.error(f"Image analysis failed for inspection {inspection_id}: {e}")
            AuditLog.log_action(
                user=user,
                action_type='inspection_analysis',
                resource_type='inspection',
                resource_id=inspection_id,
                success=False,
                error_message=str(e)
            )
            raise
    
    def _generate_vision_prompt(self, equipment_type: str, notes: str = '') -> str:
        """Generate equipment-specific vision prompt"""
        
        equipment_details = {
            'transformer': {
                'focus': 'transformer condition, oil leaks, insulation damage, overheating signs',
                'checklist': ['visual_damage', 'oil_leaks', 'overheating_signs', 'insulation_integrity', 'grounding_status']
            },
            'cable': {
                'focus': 'cable integrity, insulation damage, overheating, physical damage',
                'checklist': ['visual_damage', 'insulation_damage', 'overheating_signs', 'cable_sag', 'connection_integrity']
            },
            'meter': {
                'focus': 'meter condition, tampering signs, physical damage, connection integrity',
                'checklist': ['visual_damage', 'tampering_signs', 'display_functionality', 'seal_integrity', 'connection_security']
            },
            'pole': {
                'focus': 'structural integrity, corrosion, cracks, tilt angle, foundation condition',
                'checklist': ['structural_damage', 'corrosion', 'cracks', 'tilt_detected', 'foundation_condition']
            },
            'switchgear': {
                'focus': 'switchgear condition, arc flash hazards, insulation, mechanical integrity',
                'checklist': ['visual_damage', 'arc_flash_signs', 'insulation_condition', 'mechanical_integrity', 'safety_labeling']
            },
            'substation': {
                'focus': 'overall substation condition, equipment status, safety hazards',
                'checklist': ['equipment_damage', 'safety_hazards', 'fence_integrity', 'warning_signs', 'vegetation_clearance']
            },
            'other': {
                'focus': 'general electrical equipment condition and safety hazards',
                'checklist': ['visual_damage', 'safety_hazards', 'functional_status', 'environmental_factors']
            }
        }
        
        details = equipment_details.get(equipment_type, equipment_details['other'])
        
        prompt = f"""You are an expert electrical equipment inspector analyzing a field image of {equipment_type} equipment.

EQUIPMENT TYPE: {equipment_type}
FOCUS AREAS: {details['focus']}

{f"INSPECTOR NOTES: {notes}" if notes else ""}

Analyze the image and provide a structured assessment in JSON format:

{{
  "technical_description": "Detailed description of what you observe in the image",
  "detected_issues": ["List of specific issues identified"],
  "risk_classification": "Low|Medium|High|Critical",
  "safety_warnings": ["List of safety hazards requiring immediate attention"],
  "recommended_actions": ["List of specific recommended next steps"],
  "inspection_checklist": {{
    {', '.join([f'"{item}": "yes|no|unclear"' for item in details['checklist']])}
  }},
  "confidence_score": 0.0-1.0,
  "additional_notes": "Any additional observations"
}}

IMPORTANT:
- Use "Critical" risk only for immediate life/property threats (fire, explosion, imminent failure)
- Be specific in technical descriptions using electrical engineering terminology
- Safety warnings should be clear and actionable
- Recommended actions should be prioritized (most urgent first)
- In inspection checklist, use "yes" if issue is present, "no" if not present, "unclear" if cannot determine

Return ONLY the JSON object, no additional text.
"""
        return prompt
    
    def _call_vision_llm(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """
        Call vision-capable LLM with image
        
        Args:
            image_path: Path to image file
            prompt: Text prompt for analysis
        
        Returns:
            LLM response (parsed JSON or raw text)
        """
        # Prepare image for API
        import base64
        
        with open(image_path, 'rb') as image_file:
            image_data = base64.b64encode(image_file.read()).decode('utf-8')
        
        # Call LLM with vision capability
        # Note: This assumes  basic_llm supports vision (needs to be extended)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}"
                        }
                    }
                ]
            }
        ]
        
        response = vision_llm.call(messages=messages)
        return response
    
    def _parse_llm_output(self, llm_output: Any) -> Dict[str, Any]:
        """Parse LLM output to extract JSON structure"""
        
        # If already a dict, return it
        if isinstance(llm_output, dict):
            return llm_output
        
        # Try to extract JSON from string response
        output_str = str(llm_output)
        
        # Try to find JSON in markdown code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r'(\{.*\})', output_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Fallback: treat entire response as unstructured
                return {
                    'technical_description': output_str,
                    'detected_issues': [],
                    'risk_classification': 'medium',
                    'safety_warnings': [],
                    'recommended_actions': [],
                    'inspection_checklist': {},
                    'confidence_score': 0.5,
                    'additional_notes': 'Failed to parse structured output'
                }
        
        try:
            parsed = json.loads(json_str)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON output: {e}")
            return {
                'technical_description': output_str[:500],
                'detected_issues': [],
                'risk_classification': 'medium',
                'safety_warnings': [],
                'recommended_actions': [],
                'inspection_checklist': {},
                'confidence_score': 0.3,
                'error': f'JSON parse error: {str(e)}'
            }
    
    def _detect_emergency(self, analysis_output: Dict[str, Any]) -> bool:
        """
        Detect emergency conditions from analysis output
        
        Args:
            analysis_output: Parsed LLM output
        
        Returns:
            True if emergency detected, False otherwise
        """
        # Check risk classification
        if analysis_output.get('risk_classification', '').lower() == 'critical':
            return True
        
        # Check for emergency keywords in technical description and issues
        text_to_check = ' '.join([
            analysis_output.get('technical_description', ''),
            ' '.join(analysis_output.get('detected_issues', [])),
            ' '.join(analysis_output.get('safety_warnings', []))
        ]).lower()
        
        for keyword in self.EMERGENCY_KEYWORDS:
            if keyword in text_to_check:
                logger.warning(f"Emergency keyword detected: {keyword}")
                return True
        
        return False
    
    def _save_analysis(
        self,
        inspection: FieldInspection,
        parsed_output: Dict[str, Any],
        is_emergency: bool,
        raw_output: Any
    ) -> InspectionAnalysis:
        """Save analysis results to database"""
        
        with transaction.atomic():
            analysis = InspectionAnalysis.objects.create(
                inspection=inspection,
                technical_description=parsed_output.get('technical_description', ''),
                risk_classification=parsed_output.get('risk_classification', 'medium').lower(),
                safety_warnings='\n'.join(parsed_output.get('safety_warnings', [])),
                recommended_actions='\n'.join(parsed_output.get('recommended_actions', [])),
                inspection_checklist=parsed_output.get('inspection_checklist', {}),
                is_emergency=is_emergency,
                confidence_score=parsed_output.get('confidence_score'),
                raw_llm_output=parsed_output
            )
            
            # If emergency, log special alert
            if is_emergency:
                AuditLog.log_action(
                    user=inspection.inspector,
                    action_type='emergency_alert',
                    resource_type='inspection',
                    resource_id=inspection.id,
                    request_payload={'equipment_type': inspection.equipment_type},
                    response_summary={'risk': analysis.risk_classification},
                    success=True
                )
        
        return analysis
    
    def _format_analysis_response(self, analysis: InspectionAnalysis) -> Dict[str, Any]:
        """Format analysis for API response"""
        return {
            'inspection_id': analysis.inspection.id,
            'technical_description': analysis.technical_description,
            'risk_classification': analysis.risk_classification,
            'risk_classification_display': analysis.get_risk_classification_display(),
            'safety_warnings': analysis.safety_warnings.split('\n') if analysis.safety_warnings else [],
            'recommended_actions': analysis.recommended_actions.split('\n') if analysis.recommended_actions else [],
            'inspection_checklist': analysis.inspection_checklist,
            'is_emergency': analysis.is_emergency,
            'confidence_score': analysis.confidence_score,
            'analyzed_at': analysis.analysis_timestamp.isoformat(),
            'equipment_type': analysis.inspection.equipment_type
        }
