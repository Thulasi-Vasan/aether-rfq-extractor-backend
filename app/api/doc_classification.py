from fastapi import APIRouter, UploadFile, File, BackgroundTasks, Depends
from fastapi.exceptions import HTTPException
from fastapi.concurrency import run_in_threadpool
from app.models.classifier import ClassificationResponse, ClassificationCategory
from app.services.doc_classifier.classification import VLMClassificationService
from app.models.job import ClassificationJob
from app.core.database import SessionLocal, get_db
from sqlalchemy.orm import Session
import tempfile
import zipfile
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List, Optional
import asyncio
import json

from app.api.dependencies import get_current_user
from fastapi.responses import FileResponse

class ZipClassificationResponse(BaseModel):
    results: Dict[str, List[ClassificationResponse]]

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    results: Optional[ZipClassificationResponse] = None
    error_message: Optional[str] = None

async def classify_document(
    file: UploadFile = File(...),
) -> ClassificationResponse:
    filename = file.filename or "unknown.txt"
    ext = Path(filename).suffix.lower()
    if ext not in {".pdf", ".step", ".stp"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {ext}")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        content = await file.read()
        tmp.write(content)

    try:
        service = VLMClassificationService()
        result = await run_in_threadpool(service.classify_file, tmp_path, filename)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


async def process_zip_background(job_id: str, zip_path: Path):
    db = SessionLocal()
    try:
        job = db.query(ClassificationJob).filter(ClassificationJob.id == job_id).first()
        if job:
            job.status = "processing"
            db.commit()

        service = VLMClassificationService()
        
        results: Dict[str, List[ClassificationResponse]] = {
            "Casting": [],
            "Machining": [],
            "Assembly": [],
            "Unclassified": []
        }

        extract_dir = zip_path.parent / f"extracted_{job_id}"
        extract_dir.mkdir(exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise Exception("Invalid zip file")

        # Gather files
        valid_files = []
        for path in extract_dir.rglob("*"):
            if path.is_file():
                if path.name.startswith("._") or path.name == ".DS_Store" or "__MACOSX" in path.parts:
                    continue
                ext = path.suffix.lower()
                if ext in {".pdf", ".step", ".stp"}:
                    valid_files.append(path)

        # Batch classify using graph resolution
        from app.services.doc_classifier.classification import BatchClassificationService
        batch_service = BatchClassificationService()
        
        batch_results = await run_in_threadpool(batch_service.classify_batch, valid_files)

        for res in batch_results:
            results[res.category.value].append(res)

        if job:
            job.status = "completed"
            job.results = json.dumps({"results": {k: [v.model_dump() for v in lst] for k, lst in results.items()}})
            db.commit()
    except Exception as e:
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
    finally:
        db.close()


async def classify_zip(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
) -> JobStatusResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    # Create job in DB
    job = ClassificationJob(status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    # Store artifacts persistently
    artifacts_dir = Path("data/artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    zip_path = artifacts_dir / f"upload_{job.id}.zip"
    
    content = await file.read()
    zip_path.write_bytes(content)

    background_tasks.add_task(process_zip_background, job.id, zip_path)

    return JobStatusResponse(job_id=job.id, status=job.status)


async def get_zip_classification_status(
    job_id: str,
    db: Session = Depends(get_db)
) -> JobStatusResponse:
    job = db.query(ClassificationJob).filter(ClassificationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = JobStatusResponse(job_id=job.id, status=job.status, error_message=job.error_message)
    if job.status == "completed" and job.results:
        response.results = ZipClassificationResponse.model_validate_json(job.results)

    return response


async def get_artifact(job_id: str, filename: str):
    artifacts_dir = Path("data/artifacts")
    job_dir = artifacts_dir / f"extracted_{job_id}"
    
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job artifacts not found")

    # Search for the file by name within the specific job folder
    for path in job_dir.rglob("*"):
        if path.is_file() and path.name == filename:
            return FileResponse(path)
            
    raise HTTPException(status_code=404, detail="Artifact not found")
