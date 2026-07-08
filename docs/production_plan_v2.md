# Production Grade Plan v2: RBAC & Document Classification

This plan outlines the architecture and implementation steps to elevate the current system to production grade. It covers two primary areas: moving from mock RBAC to robust Role-Based Access Control, and implementing an expert-level Document Classification pipeline tightly coupled with UI artifact viewing.

## Phase 1: Production-Grade RBAC Control

Currently, the system relies on preset roles and hardcoded dummy hashed passwords (defaulted to "password"). We need to secure this with a robust authentication and authorization flow.

### 1.1 Backend Implementation (Python/FastAPI)
- **Database Schema**: Ensure a scalable SQLite/PostgreSQL `users` table including `id`, `email`, `name`, `role`, `hashed_password` (using bcrypt or argon2, securely salted), and `is_active`.
- **Authentication**: 
  - Implement a `POST /v1/auth/login` endpoint that securely verifies passwords against the hash.
  - Generate JWT (JSON Web Tokens) with a **12-hour expiration time**.
- **Authorization (`/me` endpoint & API-wide Validation)**:
  - Create a `GET /v1/auth/me` endpoint. Every time a page loads, the frontend will call this endpoint, sending the `userid` and JWT `auth token` in the request headers. The backend will authenticate the token and respond with the specific flags/roles (e.g., `role: "PED"`, `permissions: ["write:machining", "read:all"]`) for that user.
  - **Global API Authorization**: Update *all* backend API endpoints to require and validate the `userid` and `auth token` from the request headers. This ensures that the user is authorized to perform the requested action on the backend, enforcing RBAC at the API level (e.g., rejecting a machining update request from a "Marketing" user).
- **Password Management**:
  - Implement initial password setup/reset flows so users are forced to change the default "password" upon first login.

### 1.2 Frontend Implementation (React)
- **Session State & App Mount**: 
  - On every page load/mount, trigger a call to the `/me` API using the stored JWT and `userid` in the headers.
  - Update `useRFQStore` (or an auth store) to persist the returned flags/roles dynamically.
- **API Client Interceptor**:
  - Update the frontend API client (e.g., Axios or fetch wrapper) to automatically inject the `userid` and JWT `auth token` into the headers of *every single outbound API request*.
- **Role-Based Routing & UI Rendering**: 
  - Use the flags/roles returned from the `/me` endpoint to determine which content to show.
  - Restrict navigation to tabs based on the user's role.
  - Implement read-only/disabled states for form fields if the user lacks write access to a specific tab.
  - Conditionally render action buttons (e.g., Approve, Reject, Edit) dynamically using the permissions flags.

---

## Phase 2: Expert-Level Document Classification

We will implement the classification logic based on expert manufacturing engineering workflows (referencing the Cummins/Holset standard approach).

### 2.1 Backend: Classification Pipeline
- **Zip Extraction & Pre-processing**:
  - Strip known junk (`__MACOSX`, `.DS_Store`).
  - Normalize file grouping by Part Number. A part's PDF and its STEP/CAD files must be routed together regardless of filename deviations.
- **Step 1: Part Relationship Graph (BOM Parsing)**:
  - Before classifying, parse the BOM table from all files.
  - **Logic**: If Part A's BOM lists Part B, Part B is a raw input (Casting). If a part's BOM has multiple components, it's an Assembly.
- **Step 2: Content-Level Signals**:
  - Parse the Title Block for explicit indicators (`DRAWING CATEGORY`).
  - Analyze dimensioning content:
    - *Casting*: "AS CAST", draft angles, casting tolerances.
    - *Machining*: GD&T machined datums, "SET UP", "FACE CLEAN UP".
    - *Assembly*: Exploded views, torque specs.
- **Output & Integration**:
  - The classification agent must return a strict JSON manifest categorizing files into `Casting`, `Machining`, `Assembly`, or `Unclassified`.

### 2.2 Frontend: Synchronized Artifact Viewing
Currently, the "View Artifacts" feature is not rendering step files and pdfs correctly, and does not filter by context.

- **Tab-Specific Artifact Rendering**:
  - The frontend must filter the artifacts displayed based on the active tab context.
  - **Example**: When viewing the **Machining** tab, clicking "View Artifacts" must *strictly* display only Machining PDFs and STEP files. It should not show Casting or Assembly files.
  - **Example**: Similarly, the **Die Casting** tab only shows Casting artifacts.
- **PDF and STEP File Renderers**:
  - Integrate a robust PDF viewer (e.g., `react-pdf`) and a 3D STEP file viewer (e.g., using `three.js` or `react-three-fiber` based STEP loaders).
  - Ensure the sidebar or modal for "View Artifacts" accurately pulls from the grouped data returned by the backend classification manifest.
- **Unclassified Handling**:
  - Create a fallback view for `Unclassified` documents that requires manual human-in-the-loop assignment to a department.
