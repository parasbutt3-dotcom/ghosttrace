from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.v1.auth import limiter
from app.database import get_db
from app.models.user import User
from app.services.takeout import import_takeout

router = APIRouter(prefix="/takeout", tags=["takeout"])

MAX_BYTES = 200 * 1024 * 1024  # 200 MB upload cap


@router.post("/import")
@limiter.limit("3/hour")
async def upload_takeout(request: Request, file: UploadFile = File(...),
                         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(status_code=422, detail="upload a .zip exported from takeout.google.com")
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="takeout zip exceeds 200MB")
    result = import_takeout(db, user.id, raw)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result.get("error", "import failed"))
    return result