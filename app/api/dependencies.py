from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.cost_estimation.excel_populator import ExcelExportService
from app.services.documents.extractor import PdfExtractionService
from app.services.storage import DocumentStore


def get_store(settings: Settings = Depends(get_settings)) -> DocumentStore:
    return DocumentStore(settings)


def get_extractor(
    settings: Settings = Depends(get_settings),
    store: DocumentStore = Depends(get_store),
) -> PdfExtractionService:
    return PdfExtractionService(settings, store)


def get_excel_exporter(settings: Settings = Depends(get_settings)) -> ExcelExportService:
    return ExcelExportService(settings)

from fastapi import Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.services.auth import SECRET_KEY, ALGORITHM

security = HTTPBearer()

from typing import Optional

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    userid: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        token_userid: str = payload.get("userid")
        if not userid:
            userid = token_userid
            
        if email is None or token_userid != userid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")
        
    user = db.query(User).filter(User.id == userid).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
        
    return user
