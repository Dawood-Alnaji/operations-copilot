"""
Multi-Agent Orchestration Service

Implements CrewAI-style agent orchestration for comprehensive field inspection analysis.
Agents work sequentially, each building upon previous outputs.
"""

import logging
import json
from typing import Dict, Any, List
import time

from django.db import transaction

from field_operations.models import InspectionAnalysis, AgentReasoningLog
from core.tools import vision_llm

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates multiple AI agents for multi-perspective analysis"""
    
    # Agent definitions
    AGENTS = {
        'technical_ops': {
            'role': 'Technical Operations Specialist',
            'goal': 'Analyze equipment technical condition and identify operational issues',
            'backstory': 'You are an experienced electrical engineer with 15+ years in power distribution. You specialize in equipment diagnostics and preventive maintenance.',
        },
        'safety': {
            'role': 'Safety Compliance Officer',
            'goal': 'Identify safety hazards, code violations, and regulatory compliance issues',
            'backstory': 'You are a certified electrical safety inspector focused on worker safety and regulatory compliance. You prioritize life-threatening hazards.',
        },
        'risk': {
            'role': 'Risk Assessment Analyst',
            'goal': 'Evaluate overall risk, prioritize response actions, and estimate impact',
            'backstory': 'You are a risk management specialist who evaluates operational, safety, and financial risks. You provide data-driven priority recommendations.',
        },
        'executive': {
            'role': 'Executive Summary Generator',
            'goal': 'Synthesize findings into clear, actionable management brief',
            'backstory': 'You create concise executive summaries for senior management, highlighting critical decisions and resource allocation needs.',
        }
    }
    
    def orchestrate_analysis(self, inspection_analysis_id: int) -> Dict[str, Any]:
        """
        Run multi-agent analysis on inspection
        
        Args:
            inspection_analysis_id: ID of InspectionAnalysis to enhance
        
        Returns:
            Dict with executive summary and all agent outputs
        """
        try:
            analysis = InspectionAnalysis.objects.select_related(
                'inspection'
            ).get(id=inspection_analysis_id)
            
            logger.info(f"Starting multi-agent orchestration for analysis {inspection_analysis_id}")
            
            # Run agents sequentially
            agent_outputs = {}
            processing_order = 1
            
            # 1. Technical Operations Agent
            logger.info("Running Technical Operations Agent...")
            tech_output = self._run_technical_ops_agent(analysis)
            agent_outputs['technical_ops'] = tech_output
            self._log_agent_reasoning(analysis, 'technical_ops', tech_output, processing_order)
            processing_order += 1
            
            # 2. Safety Compliance Agent
            logger.info("Running Safety Compliance Agent...")
            safety_output = self._run_safety_agent(analysis, tech_output)
            agent_outputs['safety'] = safety_output
            self._log_agent_reasoning(analysis, 'safety', safety_output, processing_order)
            processing_order += 1
            
            # 3. Risk Assessment Agent
            logger.info("Running Risk Assessment Agent...")
            risk_output = self._run_risk_agent(analysis, tech_output, safety_output)
            agent_outputs['risk'] = risk_output
            self._log_agent_reasoning(analysis, 'risk', risk_output, processing_order)
            processing_order += 1
            
            # 4. Executive Summary Agent
            logger.info("Running Executive Summary Agent...")
            exec_output = self._run_executive_agent(analysis, agent_outputs)
            agent_outputs['executive'] = exec_output
            self._log_agent_reasoning(analysis, 'executive', exec_output, processing_order)
            
            logger.info(f"Multi-agent orchestration completed for analysis {inspection_analysis_id}")
            
            return {
                'executive_summary': exec_output,
                'detailed_analysis': agent_outputs
            }
        
        except Exception as e:
            logger.error(f"Multi-agent orchestration failed: {e}")
            raise
    
    def _run_technical_ops_agent(self, analysis: InspectionAnalysis) -> Dict[str, Any]:
        """Execute Technical Operations Agent"""
        
        agent_config = self.AGENTS['technical_ops']
        
        prompt = f"""You are a {agent_config['role']}.

BACKGROUND: {agent_config['backstory']}

GOAL: {agent_config['goal']}

INSPECTION DATA:
- Equipment Type: {analysis.inspection.equipment_type}
- Initial Assessment: {analysis.technical_description}
- Detected Issues: {', '.join(analysis.raw_llm_output.get('detected_issues', []))}
- Risk Level: {analysis.risk_classification}

TASK:
Provide a detailed technical analysis focusing on:
1. Root cause analysis of identified issues
2. Impact on power distribution operations
3. Equipment lifecycle considerations
4. Maintenance priority assessment
5. Technical specifications for repairs

Return your analysis as JSON:
{{
  "root_cause": "Description of underlying technical causes",
  "operational_impact": "How this affects power distribution",
  "equipment_condition": "Overall equipment health assessment",
  "maintenance_priority": "immediate|high|medium|low",
  "technical_recommendations": ["Specific technical actions"],
  "estimated_effort": "Time/resources estimate"
}}
"""
        
        response = vision_llm.call(messages=[
            {"role": "system", "content": f"You are a {agent_config['role']}."},
            {"role": "user", "content": prompt}
        ])
        
        return self._parse_agent_response(response, {
            "root_cause": "",
            "operational_impact": "",
            "equipment_condition": "",
            "maintenance_priority": "medium",
            "technical_recommendations": [],
            "estimated_effort": ""
        })
    
    def _run_safety_agent(
        self, 
        analysis: InspectionAnalysis, 
        tech_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Safety Compliance Agent"""
        
        agent_config = self.AGENTS['safety']
        
        prompt = f"""You are a {agent_config['role']}.

BACKGROUND: {agent_config['backstory']}

GOAL: {agent_config['goal']}

INSPECTION DATA:
- Equipment Type: {analysis.inspection.equipment_type}
- Safety Warnings: {analysis.safety_warnings}
- Risk Level: {analysis.risk_classification}
- Is Emergency: {analysis.is_emergency}

TECHNICAL ANALYSIS:
{json.dumps(tech_output, indent=2)}

TASK:
Evaluate safety and compliance aspects:
1. Identify immediate safety hazards
2. Assess regulatory compliance (electrical codes, safety standards)
3. Worker safety protocols required
4. Public safety considerations
5. Legal/liability implications

Return your analysis as JSON:
{{
  "immediate_hazards": ["List critical safety hazards"],
  "compliance_violations": ["Regulatory/code violations"],
  "required_safety_protocols": ["Safety measures for repairs"],
  "public_safety_impact": "Assessment of risk to public",
  "liability_exposure": "Legal/liability concerns",
  "safety_priority": "critical|high|medium|low"
}}
"""
        
        response = vision_llm.call(messages=[
            {"role": "system", "content": f"You are a {agent_config['role']}."},
            {"role": "user", "content": prompt}
        ])
        
        return self._parse_agent_response(response, {
            "immediate_hazards": [],
            "compliance_violations": [],
            "required_safety_protocols": [],
            "public_safety_impact": "",
            "liability_exposure": "",
            "safety_priority": "medium"
        })
    
    def _run_risk_agent(
        self,
        analysis: InspectionAnalysis,
        tech_output: Dict[str, Any],
        safety_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute Risk Assessment Agent"""
        
        agent_config = self.AGENTS['risk']
        
        prompt = f"""You are a {agent_config['role']}.

BACKGROUND: {agent_config['backstory']}

GOAL: {agent_config['goal']}

INSPECTION DATA:
- Equipment: {analysis.inspection.equipment_type}
- Initial Risk: {analysis.risk_classification}

TECHNICAL ASSESSMENT:
{json.dumps(tech_output, indent=2)}

SAFETY ASSESSMENT:
{json.dumps(safety_output, indent=2)}

TASK:
Provide comprehensive risk analysis:
1. Overall risk score and priority
2. Probability and impact assessment
3. Cascading failure risks
4. Financial impact estimation
5. Response timeline recommendation

Return analysis as JSON:
{{
  "overall_risk_score": 1-10,
  "priority_level": "critical|high|medium|low",
  "probability_of_failure": "high|medium|low",
  "potential_impact": {{
    "operational": "Description",
    "financial": "Estimated cost",
    "safety": "Safety impact",
    "reputation": "Public relations impact"
  }},
  "cascading_risks": ["Potential secondary failures"],
  "response_timeline": "immediate|24hours|1week|1month",
  "mitigation_strategy": "Recommended approach"
}}
"""
        
        response = vision_llm.call(messages=[
            {"role": "system", "content": f"You are a {agent_config['role']}."},
            {"role": "user", "content": prompt}
        ])
        
        return self._parse_agent_response(response, {
            "overall_risk_score": 5,
            "priority_level": "medium",
            "probability_of_failure": "medium",
            "potential_impact": {},
            "cascading_risks": [],
            "response_timeline": "1week",
            "mitigation_strategy": ""
        })
    
    def _run_executive_agent(
        self,
        analysis: InspectionAnalysis,
        all_agents: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Execute Executive Summary Agent"""
        
        agent_config = self.AGENTS['executive']
        
        prompt = f"""You are an {agent_config['role']}.

BACKGROUND: {agent_config['backstory']}

GOAL: {agent_config['goal']}

EQUIPMENT INSPECTION:
- Type: {analysis.inspection.equipment_type}
- Location: {analysis.inspection.location or 'Not specified'}
- Inspector: {analysis.inspection.inspector.get_full_name() or analysis.inspection.inspector.username}

MULTI-AGENT ANALYSIS:
{json.dumps(all_agents, indent=2)}

TASK:
Create concise executive summary for management:
1. One-sentence situation summary
2. Key findings (top 3 most critical)
3. Recommended immediate actions
4. Resource requirements
5. Decision needed from management

Return as JSON:
{{
  "situation_summary": "One sentence overview",
  "criticality": "critical|high|medium|low",
  "key_findings": ["Top 3 critical points"],
  "immediate_actions": ["Specific actions in priority order"],
  "resources_needed": {{
    "personnel": "Description",
    "equipment": "Description",
    "estimated_cost": "Amount",
    "estimated_time": "Duration"
  }},
  "management_decision_required": "What decision management must make",
  "recommended_decision": "What you recommend"
}}
"""
        
        response = vision_llm.call(messages=[
            {"role": "system", "content": f"You are an {agent_config['role']}."},
            {"role": "user", "content": prompt}
        ])
        
        return self._parse_agent_response(response, {
            "situation_summary": "",
            "criticality": "medium",
            "key_findings": [],
            "immediate_actions": [],
            "resources_needed": {},
            "management_decision_required": "",
            "recommended_decision": ""
        })
    
    def _parse_agent_response(
        self, 
        response: Any, 
        default_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse agent LLM response to JSON"""
        
        # If already dict, return it
        if isinstance(response, dict):
            return {**default_structure, **response}
        
        # Try to parse JSON from string
        response_str = str(response)
        
        # Extract JSON from markdown
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'(\{.*\})', response_str, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                logger.warning("Failed to extract JSON from agent response")
                return default_structure
        
        try:
            parsed = json.loads(json_str)
            return {**default_structure, **parsed}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse agent JSON: {e}")
            return default_structure
    
    def _log_agent_reasoning(
        self,
        analysis: InspectionAnalysis,
        agent_name: str,
        agent_output: Dict[str, Any],
        processing_order: int
    ):
        """Log agent reasoning to database"""
        
        agent_config = self.AGENTS[agent_name]
        
        with transaction.atomic():
            AgentReasoningLog.objects.create(
                inspection_analysis=analysis,
                agent_name=agent_name,
                agent_role=agent_config['role'],
                agent_output=agent_output,
                processing_order=processing_order
            )
