# aether-rfq-extractor-backend

FastAPI backend for extracting frontend-renderable tables from RFQ-style PDFs.

## Development

Install dependencies:

```bash
uv sync --extra dev
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

Run tests:

```bash
uv run pytest
```

## API

- `GET /health`
- `POST /v1/documents`
- `GET /v1/documents/{document_id}`
- `GET /v1/documents/{document_id}/tables`
- `GET /v1/documents/{document_id}/pages/{page_number}/tables`
- `GET /v1/documents/{document_id}/meridian`
- `GET /v1/documents/{document_id}/meridian?include_raw=true`
- `GET /v1/reference-document`
- `POST /v1/reference-document/extract`

Runtime uploads and extracted JSON are stored under `data/` by default.
