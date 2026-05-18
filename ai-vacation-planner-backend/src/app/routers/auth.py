from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_database
from app.models import User
from app.schemas.auth import UserOut, UserCreate, Token, UserLogin
from app.utils.security import get_password_hash, verify_password, create_access_token

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

@router.post("/login", response_model=Token)
def login(user: UserLogin, database: Session = Depends(get_database())):
    database_user = database.query(User).filter(User.username == user.username).first()

    if not database_user or not verify_password(user.password, database_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    access_token = create_access_token(data={"sub": str(database_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}
