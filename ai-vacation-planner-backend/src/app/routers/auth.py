from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_database
from app.models import User
from app.schemas.auth import UserOut, UserCreate
from app.utils.security import get_password_hash

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, database: Session = Depends(get_database())):
    existing_user = database.query(User).filter(
        (User.email == user.email) | (User.username == user.username)
    ).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email or Username already registered")

    hashed_password = get_password_hash(user.password)
    database_user = User(email=user.email, username=user.username, hashed_password=hashed_password)
    database.add(database_user)
    database.commit()
    database.refresh(database_user)
    return database_user