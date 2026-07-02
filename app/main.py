import logging

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import cost_estimation, documents, machining,doc_classification

from app.core.config import get_settings
from app.models import ErrorResponse
from app.services.errors import ExtractorError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)


def create_app() -> FastAPI:
    app = FastAPI(title="Aether RFQ Extractor Backend", version="0.1.0")

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ExtractorError)
    async def extractor_error_handler(_, exc: ExtractorError) -> JSONResponse:
        payload = ErrorResponse(
            error={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def fastapi_http_error_handler(request, exc: HTTPException):
        return await http_exception_handler(request, exc)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(documents.router)
    app.include_router(cost_estimation.router)
    app.include_router(machining.router)
    app.include_router(doc_classification.router)

    return app


app = create_app()
