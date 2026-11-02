from datetime import timedelta, datetime, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return password_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    data_to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_in)

    data_to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(data_to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def decode_user_id_for_logging(token: str) -> Optional[str]:
    """Best-effort decode of the user ID claim from a bearer token, for log tagging only.

    Never raises and never touches the database, so it is safe to call from
    logging middleware on every request. This is not an authentication
    check, use get_current_user for that.

    Args:
        token: The raw JWT string, without the "Bearer " prefix.

    Returns:
        The user ID claim as a string, or None if the token is missing,
        expired, or otherwise cannot be decoded.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError:
        return None