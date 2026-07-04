from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid

from app.core.database import get_db
from app.core.security import get_current_user, require_role

router = APIRouter()
UPLOAD_DIR = "app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "mp4", "docx", "mp3", "wav"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024   # 25 MB

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
            "file_url": f"/api/evidence/download/{item.evidence_id}"
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
        
    ext = (file.filename.rsplit(".", 1)[-1] if "." in file.filename else "").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type '.{ext}' is not permitted")
        
    filename = f"{crime_id}_{uuid.uuid4().hex[:8]}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    size = 0
    with open(filepath, "wb") as f:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                os.remove(filepath)
                raise HTTPException(status_code=413, detail="File exceeds 25MB limit")
            f.write(chunk)
        
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
        
    return {"success": True, "file_url": f"/api/evidence/download/{new_evidence.evidence_id}", "data": new_evidence.to_dict()}

@router.get("/download/{evidence_id}")
async def download_evidence(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    from sqlalchemy import select
    from app.models.database_models.evidence_model import Evidence

    result = await db.execute(select(Evidence).where(Evidence.evidence_id == evidence_id))
    item = result.scalar_one_or_none()
    if not item or not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Evidence not found")

    return FileResponse(item.file_path, filename=item.description)
