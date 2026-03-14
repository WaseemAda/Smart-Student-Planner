from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.db import get_session
from app.models import User
from app.schemas import UserCreate, Token
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
def register(user_in: UserCreate, session: Session = Depends(get_session)):

    print("user_in:", user_in)
    print("user_in.model_dump():", user_in.model_dump())
    print("password repr:", repr(user_in.password))
    print("password bytes:", len(user_in.password.encode("utf-8")))

    existing = session.exec(select(User).where(User.username == user_in.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")

    user = User(
        username=user_in.username,
        password_hash=hash_password(user_in.password)
    )

    session.add(user)
    session.commit()
    session.refresh(user)
    return {"ok": True}

    user = User(username=user_in.username, password_hash=hash_password(user_in.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"ok": True}

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=user.username)
    return {"access_token": token, "token_type": "bearer"}