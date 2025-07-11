from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import alert_crud
from app.models.alert import Alert


class AlertService:
    def __init__(self):
        self.logger = logger
    
    async def ingest_alert(self, db: AsyncSession, alert_data: Dict[str, Any]) -> Alert:
        """
        Ingest a new alert from monitoring systems
        
        Args:
            db: Database session
            alert_data: Alert data from monitoring system
            
        Returns:
            Created Alert object
        """
        try:
            # Validate required fields
            required_fields = ['monitoring_system', 'host_name', 'service_name', 
                             'alert_name', 'severity', 'message']
            
            for field in required_fields:
                if field not in alert_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Generate unique ID
            alert_data['id'] = str(uuid.uuid4())
            
            # Set default values
            alert_data.setdefault('status', 'active')
            alert_data.setdefault('timestamp', datetime.utcnow())
            alert_data.setdefault('created_at', datetime.utcnow())
            
            # Normalize host and service names
            alert_data['host_name'] = alert_data['host_name'].strip().lower()
            alert_data['service_name'] = alert_data['service_name'].strip().lower()
            
            # Create alert in database
            alert = await alert_crud.create_alert(db, alert_data)
            
            self.logger.info(f"Alert ingested successfully: {alert.id}")
            return alert
            
        except Exception as e:
            self.logger.error(f"Error ingesting alert: {e}")
            raise
    
    async def get_alerts(
        self, 
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Alert]:
        """
        Get alerts with optional filtering
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            filters: Optional filters (host_name, service_name, status)
            
        Returns:
            List of Alert objects
        """
        try:
            filters = filters or {}
            alerts = await alert_crud.get_alerts(
                db,
                skip=skip,
                limit=limit,
                host_name=filters.get('host_name'),
                service_name=filters.get('service_name'),
                status=filters.get('status')
            )
            return alerts
        except Exception as e:
            self.logger.error(f"Error retrieving alerts: {e}")
            raise
    
    async def get_alert_by_id(self, db: AsyncSession, alert_id: str) -> Optional[Alert]:
        """
        Get a specific alert by ID
        
        Args:
            db: Database session
            alert_id: Alert ID
            
        Returns:
            Alert object or None
        """
        try:
            return await alert_crud.get_alert(db, alert_id)
        except Exception as e:
            self.logger.error(f"Error retrieving alert {alert_id}: {e}")
            raise
    
    async def get_ungrouped_alerts(self, db: AsyncSession) -> List[Alert]:
        """
        Get alerts that haven't been assigned to a group
        
        Args:
            db: Database session
            
        Returns:
            List of ungrouped Alert objects
        """
        try:
            return await alert_crud.get_ungrouped_alerts(db)
        except Exception as e:
            self.logger.error(f"Error retrieving ungrouped alerts: {e}")
            raise
    
    def validate_alert_data(self, alert_data: Dict[str, Any]) -> bool:
        """
        Validate alert data structure
        
        Args:
            alert_data: Alert data to validate
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        required_fields = [
            'monitoring_system', 'host_name', 'service_name',
            'alert_name', 'severity', 'message'
        ]
        
        for field in required_fields:
            if field not in alert_data or not alert_data[field]:
                raise ValueError(f"Missing or empty required field: {field}")
        
        # Validate severity levels
        valid_severities = ['critical', 'high', 'medium', 'low', 'info']
        if alert_data['severity'].lower() not in valid_severities:
            raise ValueError(f"Invalid severity: {alert_data['severity']}")
        
        return True
    
    def normalize_alert_data(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize alert data for consistent processing
        
        Args:
            alert_data: Raw alert data
            
        Returns:
            Normalized alert data
        """
        normalized = alert_data.copy()
        
        # Normalize string fields
        string_fields = ['host_name', 'service_name', 'alert_name', 'severity']
        for field in string_fields:
            if field in normalized:
                normalized[field] = str(normalized[field]).strip()
        
        # Normalize severity to lowercase
        if 'severity' in normalized:
            normalized['severity'] = normalized['severity'].lower()
        
        return normalized


# Create service instance
alert_service = AlertService()
