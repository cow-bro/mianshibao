from io import BytesIO

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.services.resume_service import ResumeService

router = APIRouter()
service = ResumeService()


@router.post("/upload", summary="Upload resume file to MinIO")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    resume = await service.upload_resume(db=db, user=current_user, file=file)
    return success_response(
        data={
            "resume_id": resume.id,
            "file_url": resume.file_url,
            "file_name": resume.file_name,
        }
    )


@router.post("/{resume_id}/parse", summary="Parse uploaded resume")
async def parse_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    parsed = await service.parse_resume(db=db, user=current_user, resume_id=resume_id)
    return success_response(data=parsed)


@router.post("/{resume_id}/score", summary="Score resume with HR dimensions")
async def score_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    result = await service.score_resume(db=db, user=current_user, resume_id=resume_id)
    return success_response(data=result.model_dump())


@router.post("/{resume_id}/optimize", summary="Optimize resume with STAR method")
async def optimize_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    result = await service.optimize_resume(db=db, user=current_user, resume_id=resume_id)
    return success_response(data=result.model_dump())


@router.get("/{resume_id}/download-optimized", summary="Download optimized resume")
async def download_optimized_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> StreamingResponse:
    content, filename = await service.download_optimized_resume(db=db, user=current_user, resume_id=resume_id)
    return StreamingResponse(
        BytesIO(content),
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
