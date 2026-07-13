from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import os
import uuid

from app.core.database import get_db
from app.core.security import get_current_user, require_role

router = APIRouter()
UPLOAD_DIR = os.environ.get("EVIDENCE_UPLOAD_DIR", "/app/uploads")
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
    from app.models.database_models.crime_model import Crime
    from app.core.security import scope_district_filter
    
    try:
        uuid.UUID(crime_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid crime_id")
        
    query = select(Evidence).join(Crime, Evidence.crime_id == Crime.crime_id).where(Evidence.crime_id == crime_id)
    query = scope_district_filter(query, current_user, Crime.district_id)
    
    result = await db.execute(query)
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
    
    first_chunk = await file.read(2048)
    if not first_chunk:
        raise HTTPException(status_code=400, detail="File is empty")
        
    # Basic magic byte validation to prevent extension spoofing
    magic_signatures = {
        "jpg": [b"\xff\xd8\xff"], "jpeg": [b"\xff\xd8\xff"],
        "png": [b"\x89PNG\r\n\x1a\n"], "pdf": [b"%PDF-"],
        "mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xfa", b"\xff\xf2"],
    }
    
    is_valid = True
    if ext in magic_signatures:
        is_valid = any(first_chunk.startswith(sig) for sig in magic_signatures[ext])
    elif ext == "docx":
        is_valid = first_chunk.startswith(b"PK\x03\x04") and any(marker in first_chunk for marker in [b"word/", b"[Content_Types].xml", b"docProps"])
    elif ext == "mp4":
        is_valid = b"ftyp" in first_chunk[:32] or b"moov" in first_chunk[:32] or b"mdat" in first_chunk[:32]
    elif ext == "wav":
        is_valid = first_chunk.startswith(b"RIFF") and b"WAVE" in first_chunk[:16]
        
    if not is_valid:
        raise HTTPException(status_code=400, detail="File content does not match its extension (magic bytes mismatch)")
        
    size = len(first_chunk)
    with open(filepath, "wb") as f:
        f.write(first_chunk)
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
    from app.models.database_models.crime_model import Crime
    from app.core.security import scope_district_filter

    query = select(Evidence).join(Crime, Evidence.crime_id == Crime.crime_id).where(Evidence.evidence_id == evidence_id)
    query = scope_district_filter(query, current_user, Crime.district_id)

    result = await db.execute(query)
    item = result.scalar_one_or_none()
    if not item or not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Evidence not found")

    return FileResponse(item.file_path, filename=item.description)
