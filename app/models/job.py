import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime
from app.core.database import Base

class ClassificationJob(Base):
    __tablename__ = "classification_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(String, default="pending")  # pending, processing, completed, failed
    results = Column(String, nullable=True)     # serialized JSON
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
