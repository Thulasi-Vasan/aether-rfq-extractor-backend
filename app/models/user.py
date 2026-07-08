import uuid
from sqlalchemy import Column, String, Boolean
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True)
    name = Column(String)
    role = Column(String)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
