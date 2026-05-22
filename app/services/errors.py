class ExtractorError(Exception):
    status_code = 422
    code = "extraction_failed"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidPdfError(ExtractorError):
    status_code = 400
    code = "invalid_pdf"


class EncryptedPdfError(ExtractorError):
    status_code = 409
    code = "encrypted_pdf"


class DocumentNotFoundError(ExtractorError):
    status_code = 404
    code = "document_not_found"
