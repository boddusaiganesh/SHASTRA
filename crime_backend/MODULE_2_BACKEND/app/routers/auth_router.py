from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.redis_connection import blacklist_token
from app.services.auth_service import authenticate_user, create_user_token

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token"""
    user = await authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token_data = await create_user_token(user)
    return {"success": True, "data": token_data}

@router.post("/logout")
async def logout(current_user=Depends(get_current_user)):
    """Invalidate the current JWT token"""
    await blacklist_token(current_user["token"])
    return {"success": True, "message": "Logged out successfully"}

@router.get("/verify-token")
async def verify_token(current_user=Depends(get_current_user)):
    """Verify the current JWT token is valid"""
    return {
        "success": True, 
        "data": {
            "auth_token": current_user["token"],
            "user_id": current_user["user_id"],
            "user_name": current_user["username"],
            "user_role": current_user["role"],
            "user_district": current_user["district_id"],
            "permissions_list": current_user["permissions"]
        }
    }
