# RBAC & Session Management Implementation Plan

This document outlines the proposed technical implementation to migrate Role-Based Access Control (RBAC) from the frontend mock to a persistent backend database, and to introduce robust session management.

## 1. Backend Database Integration

Currently, the RBAC rules and demo accounts are hardcoded into the React frontend. We will move this responsibility to the Python backend to ensure secure, centralized user management.

### Database Choice
- **SQLite (via SQLAlchemy):** We will use SQLite for simplicity and portability, leveraging `SQLAlchemy` as the ORM. This is easily upgradable to PostgreSQL if needed in the future.

### Schema Design
Create a `users` table:
```python
class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)  # UUID
    email = Column(String, unique=True, index=True)
    name = Column(String)
    role = Column(String)  # 'PED', 'Marketing', 'DieCasting', 'Purchase', 'Finance'
    hashed_password = Column(String)
```

### Initial Seed Data
A migration script or startup hook will automatically seed the database with the requested demo accounts (e.g., `ped@acme.com`, `marketing@acme.com`).

## 2. Secure Session Handling

Currently, when the user refreshes the page or generates a new RFQ quote, the frontend state might lose the user's role (leading to "blank" or unauthorized states). We will implement a proper session flow.

### Backend Endpoints
- `POST /v1/auth/login`: Accepts `username` and `password`. Validates against the SQLite database. On success, returns a standard JWT (JSON Web Token).
- `GET /v1/auth/me`: Validates the provided JWT (via `Authorization: Bearer <token>` header) and returns the logged-in user's `email`, `name`, and `role`.

### Frontend Updates
1. **API Client Update:** 
   Configure the API client (or `fetch` wrappers in `api.ts`) to automatically attach the JWT token from `localStorage` to all outbound requests.
2. **Persistent Store:** 
   Update `useRFQStore` to persist the `currentUserRole` and `user` profile using `zustand/middleware/persist` so that the role survives page reloads and cross-tab navigation.
3. **Session Hydration:**
   In `App.tsx` or a top-level wrapper, trigger a silent `GET /v1/auth/me` call on mount to validate the token. If it's valid, hydrate the store; if invalid, redirect the user to `/login`.
4. **New RFQ Handling:**
   When the user creates a new RFQ quote or resets the workspace, the `rfqStore` will only clear the `formData` and `tabProgress`, intentionally preserving the `user` and `currentUserRole` state.

## 3. Execution Phases
1. **Phase A (Backend):** Install SQLAlchemy, create models, write the seed script, and implement the `/auth` endpoints.
2. **Phase B (Frontend):** Update `login.tsx` to call `/v1/auth/login`. Implement the `persist` middleware in `rfqStore.ts`.
3. **Phase C (Testing):** Validate that the user role remains intact across hard refreshes and when returning to the dashboard to start a new RFQ process.

---

*Please click **Proceed** if you approve this plan, and I will execute these changes immediately.*
