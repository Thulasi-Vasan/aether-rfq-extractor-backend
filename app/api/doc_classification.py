from fastapi import APIRouter, UploadFile, File
from fastapi.exceptions import HTTPException
from fastapi.concurrency import run_in_threadpool
from app.models.classifier import ClassificationResponse, ClassificationCategory
from app.services.doc_classifier.classification import VLMClassificationService
import tempfile
import zipfile
from pathlib import Path
from pydantic import BaseModel
from typing import Dict, List
import asyncio

router = APIRouter()

class ZipClassificationResponse(BaseModel):
    results: Dict[str, List[ClassificationResponse]]

@router.post("/v1/documents/classify", response_model=ClassificationResponse)
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


@router.post("/v1/documents/classify-zip", response_model=ZipClassificationResponse)
async def classify_zip(
    file: UploadFile = File(...),
) -> ZipClassificationResponse:
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are supported")

    service = VLMClassificationService()
    
    results: Dict[str, List[ClassificationResponse]] = {
        "Casting": [],
        "Machining": [],
        "Assembly": [],
        "Unclassified": []
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = Path(tmpdir) / "upload.zip"
        content = await file.read()
        zip_path.write_bytes(content)

        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid zip file")

        # Gather files
        valid_files = []
        for path in extract_dir.rglob("*"):
            if path.is_file():
                if path.name.startswith("._") or path.name == ".DS_Store" or "__MACOSX" in path.parts:
                    continue
                ext = path.suffix.lower()
                if ext in {".pdf", ".step", ".stp"}:
                    valid_files.append(path)

        async def classify_single(p: Path):
            try:
                # Need to use threadpool since it's blocking (uses boto3)
                res = await run_in_threadpool(service.classify_file, p, p.name)
                return res
            except Exception as e:
                print(f"Classification failed for {p.name}: {str(e)}")
                # Fallback to Unclassified
                return ClassificationResponse(
                    filename=p.name,
                    category=ClassificationCategory.unclassified,
                    confidence=0.0,
                    reasoning=f"Error classifying file: {str(e)}"
                )

        tasks = [classify_single(p) for p in valid_files]
        batch_results = await asyncio.gather(*tasks)

        for res in batch_results:
            results[res.category.value].append(res)

    return ZipClassificationResponse(results=results)

