from sqlalchemy import Column, String, DateTime, Text, JSON, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.models.alert import Base


class AlertGroup(Base):
    __tablename__ = "alert_groups"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    host_name = Column(String(255), nullable=False, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    group_key = Column(String(255), nullable=False, unique=True, index=True)
    alert_count = Column(Integer, default=0)
    severity_summary = Column(JSON, nullable=True)
    status = Column(String(50), default="active")
    rca_generated = Column(String(50), default="pending")  # pending, completed, failed
    rca_content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    alerts = relationship("Alert", back_populates="group")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "host_name": self.host_name,
            "service_name": self.service_name,
            "group_key": self.group_key,
            "alert_count": self.alert_count,
            "severity_summary": self.severity_summary,
            "status": self.status,
            "rca_generated": self.rca_generated,
            "rca_content": self.rca_content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def generate_group_key(cls, host_name: str, service_name: str) -> str:
        """Generate a unique key for grouping alerts by host and service"""
        return f"{host_name}:{service_name}".lower()
