from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.database.connection import get_db_session
from app.services.grouping_service import grouping_service
from app.services.rag_service import rag_service
from app.services.rca_service import rca_service
from app.database.crud import group_crud

router = APIRouter()


class AlertGroupResponse(BaseModel):
    id: str
    name: str
    host_name: str
    service_name: str
    group_key: str
    alert_count: int
    severity_summary: Optional[Dict[str, int]]
    status: str
    rca_generated: str
    rca_content: Optional[str]
    created_at: str
    updated_at: str
    alerts: Optional[List[Dict[str, Any]]] = None


class GroupListResponse(BaseModel):
    groups: List[AlertGroupResponse]
    total: int
    skip: int
    limit: int


class GroupCreationResponse(BaseModel):
    created_groups: List[AlertGroupResponse]
    total_created: int
    message: str


@router.post("/create", response_model=GroupCreationResponse)
async def create_groups_from_alerts(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create alert groups from ungrouped alerts based on host and service name
    """
    try:
        # Create groups from ungrouped alerts
        created_groups = await grouping_service.create_groups_from_alerts(db)
        
        if not created_groups:
            return GroupCreationResponse(
                created_groups=[],
                total_created=0,
                message="No ungrouped alerts found to create groups"
            )
        
        # Add groups to knowledge base in background
        for group in created_groups:
            background_tasks.add_task(add_group_to_knowledge_base, group.id)
        
        group_responses = []
        for group in created_groups:
            group_data = group.to_dict()
            group_responses.append(AlertGroupResponse(**group_data))
        
        return GroupCreationResponse(
            created_groups=group_responses,
            total_created=len(created_groups),
            message=f"Successfully created {len(created_groups)} alert groups"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=GroupListResponse)
async def get_groups(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    include_alerts: bool = Query(False, description="Include alerts in response"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get alert groups with optional filtering
    """
    try:
        groups = await grouping_service.get_groups(db, skip=skip, limit=limit, status=status)
        
        group_responses = []
        for group in groups:
            group_data = group.to_dict()
            
            if include_alerts and group.alerts:
                group_data['alerts'] = [alert.to_dict() for alert in group.alerts]
            
            group_responses.append(AlertGroupResponse(**group_data))
        
        return GroupListResponse(
            groups=group_responses,
            total=len(group_responses),
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}", response_model=AlertGroupResponse)
async def get_group(
    group_id: str,
    include_alerts: bool = Query(True, description="Include alerts in response"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific alert group by ID
    """
    try:
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        group_data = group.to_dict()
        
        if include_alerts and group.alerts:
            group_data['alerts'] = [alert.to_dict() for alert in group.alerts]
        
        return AlertGroupResponse(**group_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/{group_id}/generate-rca")
async def generate_group_rca(
    group_id: str,
    background_tasks: BackgroundTasks,
    force_regenerate: bool = Query(False, description="Force regenerate RCA even if it exists"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Generate RCA for a specific alert group
    """
    try:
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        # Check if RCA already exists and force_regenerate is False
        if group.rca_generated == "completed" and group.rca_content and not force_regenerate:
            return {
                "message": "RCA already exists for this group",
                "group_id": group_id,
                "rca_status": "completed",
                "rca_content": group.rca_content
            }
        
        # Start RCA generation in background
        background_tasks.add_task(generate_rca_background, group_id)
        
        # Update status to indicate RCA generation started
        await group_crud.update_group_rca(db, group_id, "", "generating")
        
        return {
            "message": "RCA generation started",
            "group_id": group_id,
            "rca_status": "generating"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{group_id}/rca-status")
async def get_rca_status(
    group_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get RCA generation status for a group
    """
    try:
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        return {
            "group_id": group_id,
            "rca_status": group.rca_generated,
            "has_rca_content": bool(group.rca_content),
            "last_updated": group.updated_at.isoformat() if group.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/{group_id}")
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Delete an alert group (this will ungroup the alerts)
    """
    try:
        group = await grouping_service.get_group_by_id(db, group_id)
        
        if not group:
            raise HTTPException(status_code=404, detail="Alert group not found")
        
        # Ungroup all alerts (set group_id to None)
        if group.alerts:
            for alert in group.alerts:
                await alert_crud.update_alert_group(db, alert.id, None)
        
        # Delete the group (would need to implement this in crud)
        # For now, just mark as inactive
        await group_crud.update_group_rca(db, group_id, "", "deleted")
        
        return {
            "message": f"Group {group_id} deleted successfully",
            "ungrouped_alerts": len(group.alerts) if group.alerts else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats/summary")
async def get_group_statistics(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get group statistics summary
    """
    try:
        # Get all groups
        groups = await grouping_service.get_groups(db, limit=1000)
        
        # Calculate statistics
        total_groups = len(groups)
        status_counts = {}
        rca_status_counts = {}
        severity_distribution = {}
        avg_alerts_per_group = 0
        
        total_alerts_in_groups = 0
        
        for group in groups:
            # Status distribution
            status_counts[group.status] = status_counts.get(group.status, 0) + 1
            
            # RCA status distribution
            rca_status_counts[group.rca_generated] = rca_status_counts.get(group.rca_generated, 0) + 1
            
            # Alert count
            total_alerts_in_groups += group.alert_count
            
            # Severity distribution
            if group.severity_summary:
                for severity, count in group.severity_summary.items():
                    severity_distribution[severity] = severity_distribution.get(severity, 0) + count
        
        if total_groups > 0:
            avg_alerts_per_group = total_alerts_in_groups / total_groups
        
        return {
            "total_groups": total_groups,
            "total_alerts_in_groups": total_alerts_in_groups,
            "average_alerts_per_group": round(avg_alerts_per_group, 2),
            "status_distribution": status_counts,
            "rca_status_distribution": rca_status_counts,
            "severity_distribution": severity_distribution
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# Background task functions
async def add_group_to_knowledge_base(group_id: str):
    """Background task to add group to knowledge base"""
    try:
        from app.database.connection import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            group = await grouping_service.get_group_by_id(db, group_id)
            if group and group.alerts:
                await rag_service.add_group_to_knowledge_base(group, group.alerts)
    except Exception as e:
        print(f"Error adding group {group_id} to knowledge base: {e}")


async def generate_rca_background(group_id: str):
    """Background task to generate RCA"""
    try:
        from app.database.connection import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            group = await grouping_service.get_group_by_id(db, group_id)
            if group and group.alerts:
                rca_report = await rca_service.generate_rca(group, group.alerts)
                
                if rca_report.get("status") == "completed":
                    # Save RCA content
                    rca_content = rca_report.get("rca_analysis", "")
                    await group_crud.update_group_rca(db, group_id, rca_content, "completed")
                else:
                    # Mark as failed
                    error_msg = rca_report.get("error", "Unknown error")
                    await group_crud.update_group_rca(db, group_id, f"Error: {error_msg}", "failed")
                    
    except Exception as e:
        # Mark as failed
        from app.database.connection import AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await group_crud.update_group_rca(db, group_id, f"Error: {str(e)}", "failed")
        print(f"Error generating RCA for group {group_id}: {e}")
