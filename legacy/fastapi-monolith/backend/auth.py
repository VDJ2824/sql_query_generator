"""Authentication helpers for password hashing and JWT handling."""

from datetime import datetime, timedelta, timezone
import os

from dotenv import load_dotenv
from jose import jwt
from passlib.context import CryptContext


load_dotenv()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_secret_key() -> str:
    """Read the JWT secret from the environment."""
    return os.getenv("SECRET_KEY", "change-me-in-development")


def get_algorithm() -> str:
    return os.getenv("ALGORITHM", "HS256")


def get_access_token_expire_minutes() -> int:
    return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_minutes: int = 60) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, get_secret_key(), algorithm=get_algorithm())


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
