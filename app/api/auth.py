from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import jwt

from app.core.database import get_db
from app.models.user import User
from app.services.auth import (
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    SECRET_KEY,
    ALGORITHM
)

security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    userid: str
    
class UserProfile(BaseModel):
    email: str
    name: str
    role: str
    permissions: list[str]

def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email, "userid": user.id}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "userid": user.id}

from fastapi import Header

def get_role_permissions(role: str) -> list[str]:
    if role == "PED":
        return ["read:all", "write:machining", "write:basicDetails", "write:packaging"]
    elif role == "Marketing":
        return ["read:all", "write:businessFeasibility"]
    elif role == "DieCasting":
        return ["read:all", "write:dieDesign"]
    elif role == "Purchase":
        return ["read:all", "write:assembly"]
    elif role == "Finance":
        return ["read:all", "write:costEstimator", "write:pdfOverview"]
    return ["read:all"]

from typing import Optional

def get_me(userid: Optional[str] = Header(None), credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_userid: str = payload.get("userid")
        # Fallback if frontend fails to send userid header
        if not userid:
            userid = token_userid
            
        if email is None or token_userid != userid:
            raise HTTPException(status_code=401, detail="Invalid credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    user = db.query(User).filter(User.id == userid).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
        
    permissions = get_role_permissions(user.role)
    return {"email": user.email, "name": user.name, "role": user.role, "permissions": permissions}
