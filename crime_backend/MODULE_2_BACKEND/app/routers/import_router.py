from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.services.import_service import parse_and_import_csv, parse_and_import_json

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.post("/bulk")
@limiter.limit("2/minute")
async def bulk_import(
    request: Request,
    file: UploadFile = File(...),
    model_type: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER"])),
):
    if model_type not in ["crimes", "offenders", "victims"]:
        raise HTTPException(status_code=400, detail="Invalid model_type. Must be crimes, offenders, or victims")

    content = await file.read()
    
    if file.filename.endswith(".csv"):
        result = await parse_and_import_csv(db, content, model_type, current_user["user_id"])
    elif file.filename.endswith(".json"):
        result = await parse_and_import_json(db, content, model_type, current_user["user_id"])
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format. Use .csv or .json")
        
    from app.utils.audit import log_action
    await log_action(db, current_user["user_id"], "IMPORT", model_type.upper(), None, result)
        
    return {"success": True, "data": result}
