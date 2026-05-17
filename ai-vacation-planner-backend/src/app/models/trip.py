from datetime import timezone

from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    destination = Column(String(100), nullable=False)
    days = Column(Integer, nullable=False)
    budget = Column(Float, nullable=False)
    trip_style = Column(String(50), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    owner = relationship("User", back_populates="trips", cascade="all, delete-orphan")