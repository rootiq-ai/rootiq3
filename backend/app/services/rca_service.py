from typing import Dict, Any, List, Optional
import json
import asyncio
from datetime import datetime
from loguru import logger
import ollama

from app.config.settings import settings
from app.models.alert import Alert
from app.models.group import AlertGroup
from app.services.rag_service import rag_service


class RCAService:
    def __init__(self):
        self.logger = logger
        self.ollama_client = None
        self._initialize_ollama()
    
    def _initialize_ollama(self):
        """Initialize Ollama client"""
        try:
            # Configure Ollama client
            self.ollama_client = ollama.Client(host=settings.OLLAMA_HOST)
            
            # Test connection by checking if model exists
            models = self.ollama_client.list()
            model_names = [model['name'] for model in models['models']]
            
            if settings.OLLAMA_MODEL not in model_names:
                self.logger.warning(f"Model {settings.OLLAMA_MODEL} not found. Available models: {model_names}")
            else:
                self.logger.info(f"Ollama initialized with model: {settings.OLLAMA_MODEL}")
                
        except Exception as e:
            self.logger.error(f"Error initializing Ollama: {e}")
            # Don't raise here to allow service to start, but log the error
    
    async def generate_rca(self, group: AlertGroup, alerts: List[Alert]) -> Dict[str, Any]:
        """
        Generate Root Cause Analysis for an alert group
        
        Args:
            group: AlertGroup object
            alerts: List of Alert objects in the group
            
        Returns:
            Dictionary containing RCA analysis
        """
        try:
            self.logger.info(f"Generating RCA for group {group.id}")
            
            # Step 1: Create query for similar incidents
            query = self._create_search_query(group, alerts)
            
            # Step 2: Search for similar incidents using RAG
            similar_incidents = await rag_service.search_similar_incidents(query)
            
            # Step 3: Prepare context for LLM
            context = self._prepare_llm_context(group, alerts, similar_incidents)
            
            # Step 4: Generate RCA using LLM
            rca_analysis = await self._generate_llm_analysis(context)
            
            # Step 5: Structure the final RCA report
            rca_report = self._structure_rca_report(group, alerts, similar_incidents, rca_analysis)
            
            self.logger.info(f"RCA generated successfully for group {group.id}")
            return rca_report
            
        except Exception as e:
            self.logger.error(f"Error generating RCA for group {group.id}: {e}")
            return {
                "error": f"Failed to generate RCA: {str(e)}",
                "status": "failed"
            }
    
    def _create_search_query(self, group: AlertGroup, alerts: List[Alert]) -> str:
        """
        Create a search query for finding similar incidents
        
        Args:
            group: AlertGroup object
            alerts: List of Alert objects
            
        Returns:
            Search query string
        """
        # Combine key information for search
        query_parts = [
            f"host {group.host_name}",
            f"service {group.service_name}"
        ]
        
        # Add unique alert names
        alert_names = list(set([alert.alert_name for alert in alerts]))
        query_parts.extend(alert_names[:3])  # Limit to first 3 unique names
        
        # Add severity information
        if group.severity_summary:
            high_severity = [sev for sev, count in group.severity_summary.items() 
                           if sev in ['critical', 'high'] and count > 0]
            query_parts.extend(high_severity)
        
        return " ".join(query_parts)
    
    def _prepare_llm_context(
        self, 
        group: AlertGroup, 
        alerts: List[Alert], 
        similar_incidents: List[Dict[str, Any]]
    ) -> str:
        """
        Prepare context for LLM analysis
        
        Args:
            group: AlertGroup object
            alerts: List of Alert objects
            similar_incidents: List of similar incidents from RAG
            
        Returns:
            Formatted context string
        """
        context_parts = []
        
        # Current incident information
        context_parts.append("=== CURRENT INCIDENT ===")
        context_parts.append(f"Host: {group.host_name}")
        context_parts.append(f"Service: {group.service_name}")
        context_parts.append(f"Total Alerts: {len(alerts)}")
        context_parts.append(f"Severity Summary: {json.dumps(group.severity_summary)}")
        context_parts.append(f"Time Range: {min(alert.timestamp for alert in alerts)} to {max(alert.timestamp for alert in alerts)}")
        
        # Alert details
        context_parts.append("\n=== ALERT DETAILS ===")
        for i, alert in enumerate(alerts[:5]):  # Limit to first 5 alerts
            context_parts.append(f"Alert {i+1}:")
            context_parts.append(f"  Name: {alert.alert_name}")
            context_parts.append(f"  Severity: {alert.severity}")
            context_parts.append(f"  Message: {alert.message}")
            context_parts.append(f"  Time: {alert.timestamp}")
            if alert.details:
                context_parts.append(f"  Details: {json.dumps(alert.details)}")
        
        # Similar incidents
        if similar_incidents:
            context_parts.append("\n=== SIMILAR PAST INCIDENTS ===")
            for i, incident in enumerate(similar_incidents[:3]):  # Limit to top 3
                context_parts.append(f"Similar Incident {i+1} (Similarity: {incident['similarity_score']:.2f}):")
                context_parts.append(f"  {incident['document']}")
        
        # Limit total context length
        full_context = "\n".join(context_parts)
        if len(full_context) > settings.MAX_CONTEXT_LENGTH:
            full_context = full_context[:settings.MAX_CONTEXT_LENGTH] + "... [truncated]"
        
        return full_context
    
    async def _generate_llm_analysis(self, context: str) -> str:
        """
        Generate analysis using Ollama LLM
        
        Args:
            context: Prepared context string
            
        Returns:
            LLM generated analysis
        """
        try:
            prompt = f"""
You are an expert system administrator analyzing IT incidents. Based on the following incident data and similar past incidents, provide a comprehensive Root Cause Analysis (RCA).

{context}

Please provide a structured RCA including:

1. **Incident Summary**: Brief overview of what happened
2. **Timeline**: Key events in chronological order
3. **Root Cause Analysis**: Most likely root causes based on the evidence
4. **Contributing Factors**: Secondary factors that may have contributed
5. **Impact Assessment**: What was affected and how
6. **Recommendations**: 
   - Immediate actions to resolve the issue
   - Long-term preventive measures
7. **Similar Patterns**: Analysis of how this relates to past incidents

Be specific and actionable in your recommendations. Focus on technical details and operational insights.
"""

            response = self.ollama_client.chat(
                model=settings.OLLAMA_MODEL,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"Error generating LLM analysis: {e}")
            return f"Error generating analysis: {str(e)}"
    
    def _structure_rca_report(
        self,
        group: AlertGroup,
        alerts: List[Alert],
        similar_incidents: List[Dict[str, Any]],
        llm_analysis: str
    ) -> Dict[str, Any]:
        """
        Structure the final RCA report
        
        Args:
            group: AlertGroup object
            alerts: List of Alert objects
            similar_incidents: Similar incidents from RAG
            llm_analysis: Generated analysis from LLM
            
        Returns:
            Structured RCA report
        """
        return {
            "group_id": group.id,
            "generated_at": datetime.utcnow().isoformat(),
            "incident_summary": {
                "host": group.host_name,
                "service": group.service_name,
                "alert_count": len(alerts),
                "severity_distribution": group.severity_summary,
                "time_span": {
                    "start": min(alert.timestamp for alert in alerts).isoformat(),
                    "end": max(alert.timestamp for alert in alerts).isoformat()
                }
            },
            "similar_incidents_found": len(similar_incidents),
            "similar_incidents": [
                {
                    "similarity_score": incident['similarity_score'],
                    "metadata": incident['metadata']
                }
                for incident in similar_incidents[:3]
            ],
            "rca_analysis": llm_analysis,
            "alerts_analyzed": [
                {
                    "id": alert.id,
                    "name": alert.alert_name,
                    "severity": alert.severity,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in alerts
            ],
            "status": "completed"
        }
    
    async def quick_analysis(self, group: AlertGroup, alerts: List[Alert]) -> str:
        """
        Generate a quick analysis without full RCA process
        
        Args:
            group: AlertGroup object
            alerts: List of Alert objects
            
        Returns:
            Quick analysis string
        """
        try:
            # Create a simplified context
            alert_messages = [alert.message for alert in alerts[:3]]
            severity_counts = group.severity_summary or {}
            
            context = f"""
Quick incident analysis needed:
Host: {group.host_name}
Service: {group.service_name}
Alert Count: {len(alerts)}
Severities: {severity_counts}
Sample Messages: {'; '.join(alert_messages)}

Provide a brief analysis of this incident including likely causes and immediate actions needed.
"""
            
            response = self.ollama_client.chat(
                model=settings.OLLAMA_MODEL,
                messages=[{'role': 'user', 'content': context}]
            )
            
            return response['message']['content']
            
        except Exception as e:
            self.logger.error(f"Error generating quick analysis: {e}")
            return f"Unable to generate quick analysis: {str(e)}"


# Create service instance
rca_service = RCAService()
