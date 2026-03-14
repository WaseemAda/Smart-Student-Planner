from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# For now: hardcoded secret. Later we move to env var when deploying.
SECRET_KEY = "CHANGE_ME_TO_SOMETHING_RANDOM"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)