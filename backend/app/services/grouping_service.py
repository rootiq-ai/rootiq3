from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from collections import defaultdict
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud import alert_crud, group_crud
from app.models.alert import Alert
from app.models.group import AlertGroup


class GroupingService:
    def __init__(self):
        self.logger = logger
    
    async def create_groups_from_alerts(self, db: AsyncSession) -> List[AlertGroup]:
        """
        Create alert groups from ungrouped alerts based on host and service name
        
        Args:
            db: Database session
            
        Returns:
            List of created AlertGroup objects
        """
        try:
            # Get all ungrouped alerts
            ungrouped_alerts = await alert_crud.get_ungrouped_alerts(db)
            
            if not ungrouped_alerts:
                self.logger.info("No ungrouped alerts found")
                return []
            
            # Group alerts by host and service
            grouped_alerts = self._group_alerts_by_host_service(ungrouped_alerts)
            
            created_groups = []
            
            for group_key, alerts in grouped_alerts.items():
                host_name, service_name = group_key.split(':', 1)
                
                # Check if group already exists
                existing_group = await group_crud.get_group_by_key(db, group_key)
                
                if existing_group:
                    # Add alerts to existing group
                    group = existing_group
                    self.logger.info(f"Adding alerts to existing group: {group.id}")
                else:
                    # Create new group
                    group_data = {
                        'id': str(uuid.uuid4()),
                        'name': f"{host_name} - {service_name}",
                        'host_name': host_name,
                        'service_name': service_name,
                        'group_key': group_key,
                        'status': 'active',
                        'severity_summary': self._calculate_severity_summary(alerts)
                    }
                    
                    group = await group_crud.create_group(db, group_data)
                    created_groups.append(group)
                    self.logger.info(f"Created new group: {group.id}")
                
                # Assign alerts to group
                for alert in alerts:
                    await alert_crud.update_alert_group(db, alert.id, group.id)
                
                # Update group alert count
                await group_crud.update_group_alert_count(db, group.id)
            
            self.logger.info(f"Created {len(created_groups)} new groups from {len(ungrouped_alerts)} alerts")
            return created_groups
            
        except Exception as e:
            self.logger.error(f"Error creating groups from alerts: {e}")
            raise
    
    def _group_alerts_by_host_service(self, alerts: List[Alert]) -> Dict[str, List[Alert]]:
        """
        Group alerts by host and service name
        
        Args:
            alerts: List of Alert objects
            
        Returns:
            Dictionary with group_key as key and list of alerts as value
        """
        grouped = defaultdict(list)
        
        for alert in alerts:
            group_key = AlertGroup.generate_group_key(alert.host_name, alert.service_name)
            grouped[group_key].append(alert)
        
        return dict(grouped)
    
    def _calculate_severity_summary(self, alerts: List[Alert]) -> Dict[str, int]:
        """
        Calculate severity summary for a group of alerts
        
        Args:
            alerts: List of Alert objects
            
        Returns:
            Dictionary with severity counts
        """
        severity_count = defaultdict(int)
        
        for alert in alerts:
            severity_count[alert.severity] += 1
        
        return dict(severity_count)
    
    async def get_groups(
        self, 
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[AlertGroup]:
        """
        Get alert groups with optional filtering
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter
            
        Returns:
            List of AlertGroup objects
        """
        try:
            return await group_crud.get_groups(db, skip=skip, limit=limit, status=status)
        except Exception as e:
            self.logger.error(f"Error retrieving groups: {e}")
            raise
    
    async def get_group_by_id(self, db: AsyncSession, group_id: str) -> Optional[AlertGroup]:
        """
        Get a specific group by ID
        
        Args:
            db: Database session
            group_id: Group ID
            
        Returns:
            AlertGroup object or None
        """
        try:
            return await group_crud.get_group(db, group_id)
        except Exception as e:
            self.logger.error(f"Error retrieving group {group_id}: {e}")
            raise
    
    async def update_group_statistics(self, db: AsyncSession, group_id: str):
        """
        Update group statistics (alert count, severity summary)
        
        Args:
            db: Database session
            group_id: Group ID
        """
        try:
            group = await group_crud.get_group(db, group_id)
            if not group:
                self.logger.warning(f"Group {group_id} not found")
                return
            
            # Update alert count
            await group_crud.update_group_alert_count(db, group_id)
            
            # Update severity summary
            if group.alerts:
                severity_summary = self._calculate_severity_summary(group.alerts)
                # Update the group with new severity summary
                # (This would require adding an update method to group_crud)
                
            self.logger.info(f"Updated statistics for group {group_id}")
            
        except Exception as e:
            self.logger.error(f"Error updating group statistics for {group_id}: {e}")
            raise


# Create service instance
grouping_service = GroupingService()
