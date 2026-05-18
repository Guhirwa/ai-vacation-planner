from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_database

security = HTTPBearer

def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        database: Session = Depends(get_database())
):
    