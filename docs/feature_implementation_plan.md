# Implementation Plan: RBAC & Document Classification

## Phase 1: Frontend Role-Based Access Control (RBAC) Implementation
**Goal**: Restrict Edit and Approve access per tab based on the current user's role while preserving read-only visibility for all sections.

1. **State Management**: 
   - Update the global Zustand store (`useRFQStore`) to include a `currentUserRole` state (e.g., `'Marketing' | 'Finance' | 'PED' | 'DieCasting' | 'Purchase'`).
2. **Permission Matrix Setup**: 
   - Create a central authorization mapping object defining allowed roles per tab:
     - `basicDetails`: **PED Team**
     - `businessFeasibility`: **Marketing**
     - `documentSegregation`: **PED Team**
     - `machiningDetails`: **PED Team**
     - `packaging`: **PED Team**
     - `dieDesign` / `dieDetails`: **Die Casting Team**
     - `assembly`: **Purchase Team**
     - `costEstimator`: **Finance, PED Team**
     - `pdfOverview`: **Finance**
3. **Approval Bar Access (`workspace.tsx`)**: 
   - Modify the `HITLBar` (Human-in-the-Loop Approve/Reject bar) to evaluate the current role against the permission matrix. Hide or disable it if the user lacks access to the active tab.
4. **Read-only Tab Components**: 
   - Inject read-only/disabled states into input fields, sliders, and form components within individual tabs (e.g., `DieDesignTab`, `BasicDetailsTab`) if the `currentUserRole` doesn't match the tab's authorized roles. 

## Phase 2: Backend ZIP Extraction & Classification Integration
**Goal**: Handle bulk uploads via zip files, extracting and categorizing strictly valid files into their respective manufacturing buckets.

1. **New Endpoint (`app/main.py`)**:
   - Create a new endpoint (e.g., `POST /v1/documents/classify-zip`) specifically equipped to accept `.zip` uploads. 
2. **Extraction and Filtering Logic**:
   - Save the zip file to a temporary directory and extract it using Python's `zipfile` library.
   - Loop through the files to aggressively filter out non-target files (e.g., ignoring `.DS_Store`, `__MACOSX`, `.docx`, images) and strictly target `.pdf`, `.step`, and `.stp` file extensions.
3. **Batch Categorization (`services/classification.py`)**:
   - Pass the valid extracted files into the existing `VLMClassificationService`.
   - Implement error handling for classification timeouts, parse failures, or unrecognized engineering drawings to automatically fallback and push those specific files into the `Unclassified` category rather than failing the whole batch.
4. **Unified Response Model**: 
   - Return a JSON response aggregating the classification of all files grouped into `Casting`, `Machining`, `Assembly`, and `Unclassified`. 

## Phase 3: Frontend Document Classification Integration
**Goal**: Bridge the UI with the new backend zip classification functionality.

1. **API Client Update**:
   - Update the upload mechanism in the frontend to route `.zip` files to the newly created backend endpoint instead of handling it client-side.
2. **UI Updates (`DocumentSegregationTab.tsx`)**:
   - Bind the backend response payload to the UI components so that files organically cascade into their proper buckets (Casting, Machining, Assembly).
   - Ensure the "Unclassified" pane prominently displays files that the agent flagged as indeterminate or random edge-cases from the zip.
