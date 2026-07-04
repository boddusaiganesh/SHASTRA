from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid

from app.core.database import get_db
from app.core.security import get_current_user, require_role

router = APIRouter()
UPLOAD_DIR = "app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/{crime_id}")
async def list_evidence(
    crime_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from sqlalchemy import select
    from app.models.database_models.evidence_model import Evidence
    
    try:
        uuid.UUID(crime_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid crime_id")
        
    result = await db.execute(select(Evidence).where(Evidence.crime_id == crime_id))
    items = result.scalars().all()
    
    return {"success": True, "data": [
        {
            **item.to_dict(),
            "file_url": f"/uploads/{os.path.basename(item.file_path)}"
        } for item in items
    ]}

@router.post("/{crime_id}")
async def upload_evidence(
    crime_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"]))
):
    try:
        uuid.UUID(crime_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid crime_id")
        
    ext = file.filename.split(".")[-1]
    filename = f"{crime_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
        
    from app.models.database_models.evidence_model import Evidence
    new_evidence = Evidence(
        crime_id=crime_id,
        file_path=filepath,
        description=file.filename,
        uploaded_by=current_user["user_id"]
    )
    db.add(new_evidence)
    await db.commit()
    await db.refresh(new_evidence)
        
    return {"success": True, "file_url": f"/uploads/{filename}", "data": new_evidence.to_dict()}
