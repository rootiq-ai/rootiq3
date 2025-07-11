from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from app.models.alert import Alert
from app.models.group import AlertGroup


class AlertCRUD:
    @staticmethod
    async def create_alert(db: AsyncSession, alert_data: Dict[str, Any]) -> Alert:
        """Create a new alert"""
        alert = Alert(**alert_data)
        db.add(alert)
        await db.commit()
        await db.refresh(alert)
        return alert
    
    @staticmethod
    async def get_alert(db: AsyncSession, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_alerts(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        host_name: Optional[str] = None,
        service_name: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Alert]:
        """Get alerts with optional filtering"""
        query = select(Alert)
        
        if host_name:
            query = query.where(Alert.host_name == host_name)
        if service_name:
            query = query.where(Alert.service_name == service_name)
        if status:
            query = query.where(Alert.status == status)
            
        query = query.order_by(desc(Alert.created_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_ungrouped_alerts(db: AsyncSession) -> List[Alert]:
        """Get alerts that haven't been assigned to a group"""
        result = await db.execute(
            select(Alert).where(Alert.group_id.is_(None)).order_by(Alert.created_at)
        )
        return result.scalars().all()
    
    @staticmethod
    async def update_alert_group(db: AsyncSession, alert_id: str, group_id: str):
        """Update alert's group assignment"""
        result = await db.execute(select(Alert).where(Alert.id == alert_id))
        alert = result.scalar_one_or_none()
        if alert:
            alert.group_id = group_id
            await db.commit()


class AlertGroupCRUD:
    @staticmethod
    async def create_group(db: AsyncSession, group_data: Dict[str, Any]) -> AlertGroup:
        """Create a new alert group"""
        group = AlertGroup(**group_data)
        db.add(group)
        await db.commit()
        await db.refresh(group)
        return group
    
    @staticmethod
    async def get_group(db: AsyncSession, group_id: str) -> Optional[AlertGroup]:
        """Get group by ID with alerts"""
        result = await db.execute(
            select(AlertGroup)
            .options(selectinload(AlertGroup.alerts))
            .where(AlertGroup.id == group_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_groups(
        db: AsyncSession, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[str] = None
    ) -> List[AlertGroup]:
        """Get alert groups with optional filtering"""
        query = select(AlertGroup).options(selectinload(AlertGroup.alerts))
        
        if status:
            query = query.where(AlertGroup.status == status)
            
        query = query.order_by(desc(AlertGroup.updated_at)).offset(skip).limit(limit)
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_group_by_key(db: AsyncSession, group_key: str) -> Optional[AlertGroup]:
        """Get group by group key"""
        result = await db.execute(
            select(AlertGroup).where(AlertGroup.group_key == group_key)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_group_alert_count(db: AsyncSession, group_id: str):
        """Update the alert count for a group"""
        result = await db.execute(
            select(func.count(Alert.id)).where(Alert.group_id == group_id)
        )
        count = result.scalar()
        
        group_result = await db.execute(select(AlertGroup).where(AlertGroup.id == group_id))
        group = group_result.scalar_one_or_none()
        if group:
            group.alert_count = count
            group.updated_at = datetime.utcnow()
            await db.commit()
    
    @staticmethod
    async def update_group_rca(db: AsyncSession, group_id: str, rca_content: str, status: str = "completed"):
        """Update group with RCA content"""
        result = await db.execute(select(AlertGroup).where(AlertGroup.id == group_id))
        group = result.scalar_one_or_none()
        if group:
            group.rca_content = rca_content
            group.rca_generated = status
            group.updated_at = datetime.utcnow()
            await db.commit()


# Create instances
alert_crud = AlertCRUD()
group_crud = AlertGroupCRUD()
