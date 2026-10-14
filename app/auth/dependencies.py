from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.auth.security import decode_access_token
from backend.app.models.entities import Manager

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_manager(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Manager:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or session has expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in as a manager.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    manager_id = payload.get("sub")
    if manager_id is None:
        raise credentials_exception
    
    try:
        manager_id_int = int(manager_id)
    except ValueError:
        raise credentials_exception

    manager = db.query(Manager).filter(Manager.id == manager_id_int).first()
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager account not found",
        )
    return manager
