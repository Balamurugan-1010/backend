import os
from datetime import datetime, timedelta
from typing import Optional, Any, Union
import jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

ROOT_ENV = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"))
if os.path.exists(ROOT_ENV):
    load_dotenv(dotenv_path=ROOT_ENV, override=True)
else:
    load_dotenv()

# Secret key and algorithm configuration
JWT_SECRET = os.getenv("JWT_SECRET", "talentmatch-super-secret-jwt-key-2026-campus-recruitment")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8")[:72], salt)
    return hashed.decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
