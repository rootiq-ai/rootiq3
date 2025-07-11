from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.database.connection import get_db_session
from app.services.grouping_service import grouping_service
from app.services.rca_service import rca_service
from app.services.rag_service import rag_service

router = APIRouter()


class RCAResponse(BaseModel):
    group_id: str
    generated_at: str
    incident_summary: Dict[str, Any]
    similar_incidents_found: int
    similar_incidents: List[Dict[str, Any]]
    rca_analysis: str
    alerts_analyzed: List[Dict[str, Any]]
    status: str


class QuickAnalysisResponse(BaseModel):
    group_id: str
    analysis: str
    generated_at: str


class SimilarIncidentsResponse(BaseModel):
    query: str
    incidents: List[Dict[str, Any]]
    total_found: int


@router.get("/{group_id}", response_model=RCAResponse)
async def get_rca_for_group(
    group_id: str,
    regenerate: bool = Query(False, description="Force regenerate RCA"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get or generate RCA for a specific alert group
    """
    try:
        # Get the group with its alerts
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        if not group.alerts:
            raise HTTPException(status_code=400, detail="No alerts found in this group")
        
        # Check if RCA already exists and regenerate is False
        if (group.rca_generated == "completed" and 
            group.rca_content and 
            not regenerate):
            
            # Try to parse existing RCA content as JSON
            try:
                import json
                if group.rca_content.startswith('{'):
                    rca_data = json.loads(group.rca_content)
                    return RCAResponse(**rca_data)
                else:
                    # Legacy text format, wrap in response structure
                    return RCAResponse(
                        group_id=group_id,
                        generated_at=group.updated_at.isoformat() if group.updated_at else "",
                        incident_summary={
                            "host": group.host_name,
                            "service": group.service_name,
                            "alert_count": group.alert_count,
                            "severity_distribution": group.severity_summary or {}
                        },
                        similar_incidents_found=0,
                        similar_incidents=[],
                        rca_analysis=group.rca_content,
                        alerts_analyzed=[],
                        status="completed"
                    )
            except:
                # If parsing fails, regenerate
                pass
        
        # Generate new RCA
        rca_report = await rca_service.generate_rca(group, group.alerts)
        
        if rca_report.get("status") != "completed":
            raise HTTPException(
                status_code=500, 
                detail=f"RCA generation failed: {rca_report.get('error', 'Unknown error')}"
            )
        
        # Save the RCA to database
        import json
        rca_json = json.dumps(rca_report)
        from app.database.crud import group_crud
        await group_crud.update_group_rca(db, group_id, rca_json, "completed")
        
        return RCAResponse(**rca_report)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}/quick-analysis", response_model=QuickAnalysisResponse)
async def get_quick_analysis(
    group_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a quick analysis for an alert group without full RCA process
    """
    try:
        # Get the group with its alerts
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        if not group.alerts:
            raise HTTPException(status_code=400, detail="No alerts found in this group")
        
        # Generate quick analysis
        analysis = await rca_service.quick_analysis(group, group.alerts)
        
        from datetime import datetime
        return QuickAnalysisResponse(
            group_id=group_id,
            analysis=analysis,
            generated_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}/similar-incidents", response_model=SimilarIncidentsResponse)
async def get_similar_incidents(
    group_id: str,
    limit: int = Query(5, ge=1, le=20, description="Maximum number of similar incidents to return"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Find similar incidents for an alert group using RAG
    """
    try:
        # Get the group with its alerts
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        if not group.alerts:
            raise HTTPException(status_code=400, detail="No alerts found in this group")
        
        # Create search query
        query_parts = [
            f"host {group.host_name}",
            f"service {group.service_name}"
        ]
        
        # Add unique alert names
        alert_names = list(set([alert.alert_name for alert in group.alerts]))
        query_parts.extend(alert_names[:3])
        
        query = " ".join(query_parts)
        
        # Search for similar incidents
        similar_incidents = await rag_service.search_similar_incidents(query, limit)
        
        return SimilarIncidentsResponse(
            query=query,
            incidents=similar_incidents,
            total_found=len(similar_incidents)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/search-incidents", response_model=SimilarIncidentsResponse)
async def search_incidents(
    query: str = Field(..., description="Search query for incidents"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of incidents to return")
):
    """
    Search for incidents in the knowledge base using a custom query
    """
    try:
        # Search for incidents
        incidents = await rag_service.search_similar_incidents(query, limit)
        
        return SimilarIncidentsResponse(
            query=query,
            incidents=incidents,
            total_found=len(incidents)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/knowledge-base/stats")
async def get_knowledge_base_stats():
    """
    Get statistics about the RAG knowledge base
    """
    try:
        stats = await rag_service.get_collection_stats()
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/knowledge-base/rebuild")
async def rebuild_knowledge_base(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Rebuild the knowledge base from existing alerts and groups
    """
    try:
        # This is a potentially expensive operation
        # In production, this should be run as a background task
        
        from app.services.alert_service import alert_service
        
        # Get all alerts
        all_alerts = await alert_service.get_alerts(db, limit=10000)
        
        # Get all groups
        all_groups = await grouping_service.get_groups(db, limit=1000)
        
        # Add alerts to knowledge base
        alerts_added = 0
        for alert in all_alerts:
            try:
                await rag_service.add_alert_to_knowledge_base(alert)
                alerts_added += 1
            except Exception as e:
                print(f"Error adding alert {alert.id} to knowledge base: {e}")
        
        # Add groups to knowledge base
        groups_added = 0
        for group in all_groups:
            try:
                if group.alerts:
                    await rag_service.add_group_to_knowledge_base(group, group.alerts)
                    groups_added += 1
            except Exception as e:
                print(f"Error adding group {group.id} to knowledge base: {e}")
        
        return {
            "message": "Knowledge base rebuild completed",
            "alerts_added": alerts_added,
            "groups_added": groups_added,
            "total_documents": alerts_added + groups_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


class CustomRCARequest(BaseModel):
    alerts: List[Dict[str, Any]] = Field(..., description="List of alert data")
    context: Optional[str] = Field(None, description="Additional context for RCA")


@router.post("/generate-custom", response_model=Dict[str, Any])
async def generate_custom_rca(
    request: CustomRCARequest
):
    """
    Generate RCA for custom alert data without saving to database
    """
    try:
        if not request.alerts:
            raise HTTPException(status_code=400, detail="At least one alert is required")
        
        # Create a temporary group-like structure
        from datetime import datetime
        import uuid
        
        temp_group_data = {
            "id": str(uuid.uuid4()),
            "host_name": request.alerts[0].get("host_name", "unknown"),
            "service_name": request.alerts[0].get("service_name", "unknown"),
            "alert_count": len(request.alerts),
            "created_at": datetime.utcnow()
        }
        
        # Create temporary alert-like structures
        temp_alerts = []
        for alert_data in request.alerts:
            temp_alert = type('TempAlert', (), {
                "id": alert_data.get("id", str(uuid.uuid4())),
                "alert_name": alert_data.get("alert_name", "Unknown Alert"),
                "severity": alert_data.get("severity", "medium"),
                "message": alert_data.get("message", ""),
                "host_name": alert_data.get("host_name", "unknown"),
                "service_name": alert_data.get("service_name", "unknown"),
                "timestamp": datetime.utcnow(),
                "details": alert_data.get("details", {})
            })()
            temp_alerts.append(temp_alert)
        
        # Create temporary group
        temp_group = type('TempGroup', (), temp_group_data)()
        
        # Generate RCA
        rca_report = await rca_service.generate_rca(temp_group, temp_alerts)
        
        return rca_report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
