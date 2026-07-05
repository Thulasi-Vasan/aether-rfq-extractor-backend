# Async Zip Classification Refactoring Plan

Currently, the `POST /v1/documents/classify-zip` endpoint blocks the HTTP request while the Vision Language Model (VLM) sequentially classifies every file in the zip. For large engineering packages, this will inevitably cause HTTP timeout errors on the frontend. 

Here is the architectural plan to transition this to an asynchronous, polling-based flow.

## 1. Backend: Job State Management
We need a way to track the progress of classification jobs. Given our existing SQLite setup, we should create a new database table.

**New DB Model (`ClassificationJob`)**:
*   `job_id` (String/UUID): Primary key.
*   `status` (String): `pending`, `processing`, `completed`, or `failed`.
*   `results` (JSON): The final `ZipClassificationResponse` payload.
*   `error_message` (String): Populated if the job fails.
*   `created_at` / `updated_at` (Datetime).

## 2. Backend: API Refactoring (`app/api/doc_classification.py`)
We will split the existing endpoint into two distinct endpoints.

### Endpoint A: `POST /v1/documents/classify-zip` (Trigger)
1. Receives the `.zip` file upload.
2. Saves the `.zip` to `data/artifacts/upload_{job_id}.zip` immediately.
3. Creates a new `ClassificationJob` in the DB with status `pending`.
4. Uses FastAPI's `BackgroundTasks` (or `asyncio.create_task`) to hand off the processing function to the background.
5. **Returns immediately:** `{ "job_id": "1234-abcd", "status": "pending" }`.

### Endpoint B: `GET /v1/documents/classify-zip/{job_id}` (Polling)
1. Queries the DB for the given `job_id`.
2. Returns the current status.
3. If `status == "completed"`, includes the `results` JSON.
4. If `status == "failed"`, includes the `error_message`.

## 3. Backend: Background Worker Logic
The core logic currently residing inside `classify_zip` will be moved to a standalone async function `process_zip_background(job_id, zip_path)`.
1. Update job status to `processing`.
2. Extract the zip and filter valid `.pdf`/`.step` files.
3. Execute `VLMClassificationService` concurrently.
4. Upon completion, serialize the results and update the DB job status to `completed`.
5. Wrap the entire block in a `try/except` to ensure any crashes safely update the job status to `failed`.

## 4. Frontend: API Layer (`src/lib/api.ts`)
Update the API bindings to support the new flow:
*   Modify `classifyZip(file)` to expect a `{ job_id, status }` response.
*   Add a new function: `getZipClassificationStatus(jobId: string)`.

## 5. Frontend: UI Layer (`src/components/LeftPanel/UploadZone.tsx`)
Currently, `UploadZone` awaits the classification result directly. We will implement a polling loop:
1. User uploads the ZIP. UI changes to "Uploading...".
2. `classifyZip` returns `job_id`. UI changes to "Analyzing components...".
3. Trigger a `setInterval` or recursive polling loop every ~3 seconds calling `getZipClassificationStatus(job_id)`.
4. **On `processing`:** Keep spinning. (Optionally display elapsed time).
5. **On `completed`:** Clear interval, load the `results` into `useRFQStore`, and transition the UI to the next step.
6. **On `failed`:** Clear interval, display `toast.error(error_message)`, and reset the UI state.
