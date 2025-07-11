from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

from app.database.connection import get_db_session
from app.services.alert_service import alert_service
from app.services.rag_service import rag_service

router = APIRouter()


class AlertCreate(BaseModel):
    monitoring_system: str = Field(..., description="Name of the monitoring system")
    host_name: str = Field(..., description="Hostname where the alert originated")
    service_name: str = Field(..., description="Service name associated with the alert")
    alert_name: str = Field(..., description="Name/type of the alert")
    severity: str = Field(..., description="Alert severity (critical, high, medium, low, info)")
    message: str = Field(..., description="Alert message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional alert details")
    timestamp: Optional[datetime] = Field(None, description="Alert timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "monitoring_system": "prometheus",
                "host_name": "web-server-01",
                "service_name": "nginx",
                "alert_name": "HighCPUUsage",
                "severity": "high",
                "message": "CPU usage is above 90% for the last 5 minutes",
                "details": {
                    "cpu_percentage": 95.2,
                    "duration": "5m",
                    "threshold": 90
                },
                "timestamp": "2025-07-11T10:30:00Z"
            }
        }


class AlertResponse(BaseModel):
    id: str
    monitoring_system: str
    host_name: str
    service_name: str
    alert_name: str
    severity: str
    status: str
    message: str
    details: Optional[Dict[str, Any]]
    timestamp: Optional[str]
    created_at: str
    updated_at: str
    group_id: Optional[str]


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    skip: int
    limit: int


@router.post("/ingest", response_model=AlertResponse)
async def ingest_alert(
    alert_data: AlertCreate,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Ingest a new alert from monitoring systems
    """
    try:
        # Validate alert data
        alert_dict = alert_data.model_dump()
        alert_service.validate_alert_data(alert_dict)
        
        # Normalize alert data
        normalized_data = alert_service.normalize_alert_data(alert_dict)
        
        # Create alert
        alert = await alert_service.ingest_alert(db, normalized_data)
        
        # Add to knowledge base for RAG
        try:
            await rag_service.add_alert_to_knowledge_base(alert)
        except Exception as e:
            # Log error but don't fail the request
            print(f"Warning: Failed to add alert to knowledge base: {e}")
        
        return AlertResponse(**alert.to_dict())
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/", response_model=AlertListResponse)
async def get_alerts(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    host_name: Optional[str] = Query(None, description="Filter by host name"),
    service_name: Optional[str] = Query(None, description="Filter by service name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get alerts with optional filtering
    """
    try:
        filters = {}
        if host_name:
            filters['host_name'] = host_name.lower()
        if service_name:
            filters['service_name'] = service_name.lower()
        if status:
            filters['status'] = status
        
        alerts = await alert_service.get_alerts(db, skip=skip, limit=limit, filters=filters)
        
        alert_responses = [AlertResponse(**alert.to_dict()) for alert in alerts]
        
        return AlertListResponse(
            alerts=alert_responses,
            total=len(alert_responses),
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get a specific alert by ID
    """
    try:
        alert = await alert_service.get_alert_by_id(db, alert_id)
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return AlertResponse(**alert.to_dict())
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/ungrouped/list")
async def get_ungrouped_alerts(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get alerts that haven't been assigned to a group
    """
    try:
        alerts = await alert_service.get_ungrouped_alerts(db)
        
        alert_responses = [AlertResponse(**alert.to_dict()) for alert in alerts]
        
        return {
            "ungrouped_alerts": alert_responses,
            "count": len(alert_responses)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch-ingest")
async def batch_ingest_alerts(
    alerts_data: List[AlertCreate],
    db: AsyncSession = Depends(get_db_session)
):
    """
    Ingest multiple alerts in batch
    """
    try:
        created_alerts = []
        errors = []
        
        for i, alert_data in enumerate(alerts_data):
            try:
                # Validate and normalize
                alert_dict = alert_data.model_dump()
                alert_service.validate_alert_data(alert_dict)
                normalized_data = alert_service.normalize_alert_data(alert_dict)
                
                # Create alert
                alert = await alert_service.ingest_alert(db, normalized_data)
                created_alerts.append(AlertResponse(**alert.to_dict()))
                
                # Add to knowledge base
                try:
                    await rag_service.add_alert_to_knowledge_base(alert)
                except Exception as e:
                    print(f"Warning: Failed to add alert {alert.id} to knowledge base: {e}")
                
            except Exception as e:
                errors.append({
                    "index": i,
                    "error": str(e),
                    "alert_data": alert_data.model_dump()
                })
        
        return {
            "created_alerts": created_alerts,
            "successful_count": len(created_alerts),
            "errors": errors,
            "error_count": len(errors)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/stats/summary")
async def get_alert_statistics(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get alert statistics summary
    """
    try:
        # Get recent alerts (last 100)
        recent_alerts = await alert_service.get_alerts(db, limit=100)
        
        # Calculate statistics
        total_alerts = len(recent_alerts)
        severity_counts = {}
        status_counts = {}
        host_counts = {}
        service_counts = {}
        
        for alert in recent_alerts:
            # Severity distribution
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
            
            # Status distribution
            status_counts[alert.status] = status_counts.get(alert.status, 0) + 1
            
            # Host distribution
            host_counts[alert.host_name] = host_counts.get(alert.host_name, 0) + 1
            
            # Service distribution
            service_counts[alert.service_name] = service_counts.get(alert.service_name, 0) + 1
        
        return {
            "total_alerts": total_alerts,
            "severity_distribution": severity_counts,
            "status_distribution": status_counts,
            "top_hosts": dict(sorted(host_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
            "top_services": dict(sorted(service_counts.items(), key=lambda x: x[1], reverse=True)[:10])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
