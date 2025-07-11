from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()


class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    monitoring_system = Column(String(100), nullable=False)
    host_name = Column(String(255), nullable=False, index=True)
    service_name = Column(String(255), nullable=False, index=True)
    alert_name = Column(String(255), nullable=False)
    severity = Column(String(50), nullable=False)
    status = Column(String(50), default="active")
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Foreign key to alert group
    group_id = Column(String, ForeignKey("alert_groups.id"), nullable=True, index=True)
    
    # Relationship
    group = relationship("AlertGroup", back_populates="alerts")
    
    def to_dict(self):
        return {
            "id": self.id,
            "monitoring_system": self.monitoring_system,
            "host_name": self.host_name,
            "service_name": self.service_name,
            "alert_name": self.alert_name,
            "severity": self.severity,
            "status": self.status,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "group_id": self.group_id
        }
