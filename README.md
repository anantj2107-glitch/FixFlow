# FixFlow — Multilingual Hostel Maintenance Intelligence Platform

FixFlow helps hostel residents report maintenance issues and gives operations teams a clear queue for assignment and resolution.

## Phase 2: authentication and roles

Version 2 is a responsive web application served by FastAPI. Tickets persist in a local SQLite database at `backend/fixflow.db`.

- Resident: submit and track a maintenance request.
- Operations: review, filter, assign, resolve, or reopen requests.
- Technician: see active assigned work and resolve it.
- Registration/login: Argon2 password hashing and expiring JWT access tokens.
- Roles: `resident`, `technician`, `warden`, `admin`; backend checks every protected action.
- Public registration: resident only. Staff accounts use local CLI bootstrap.
- Triage: transparent priority rules plus persisted same-category/same-block duplicate flags.
- Responsive UI: works on desktop and mobile browser sizes.

## Run locally

From this folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item .env.example .env
# Edit .env. Replace JWT_SECRET with output from next command.
py -c "import secrets; print(secrets.token_urlsafe(48))"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

API documentation is available at `http://127.0.0.1:8000/docs`.

Create staff accounts locally; password prompts never echo:

```powershell
.\.venv\Scripts\python.exe -m backend.app.create_user --email tech@example.com --name "Tech User" --role technician
.\.venv\Scripts\python.exe -m backend.app.create_user --email warden@example.com --name "Warden User" --role warden
```

Run focused tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth_rbac
```

To restore the supplied demo data during development, stop the server and delete `backend/fixflow.db`; starting the server again will seed the sample tickets.

## Final-stage architecture

```text
Resident PWA / web portal
          |
     FastAPI backend
          |
 PostgreSQL + object storage
          |
 ML service: classification, duplicate embeddings, SLA risk scoring
          |
 Admin dashboard and technician workspace
```

## Planned production modules

1. PostgreSQL persistence for deployed multi-user use.
2. Image attachments with secure storage.
3. Local multilingual sentence embeddings for duplicate detection.
4. Small supervised category classifier trained on labelled hostel reports.
5. Notifications, activity history, SLA policies, and analytics.

## Practical ML plan

Start with 300–600 reviewed reports in 6–8 categories. Keep a test set that is never used for training. Report category macro-F1 and duplicate-match precision. The product remains useful even when the model is uncertain: it can show a suggested category and let staff correct it.

## Repository layout

```text
FixFlow/
  index.html              # Responsive application shell
  css/styles.css          # Responsive design system
  js/data.js              # Browser configuration and categories
  js/app.js               # API-connected views and workflow
  backend/app/main.py     # FastAPI auth, RBAC, SQLite persistence, static hosting
  backend/app/create_user.py # Local-only technician/warden/admin bootstrap
  .env.example            # Required environment keys; no secrets
  backend/fixflow.db      # Local data, created on first server start
  ml/                     # Data, evaluation, and model roadmap
  docs/                   # Product delivery roadmap
  README.md               # Architecture and run guide
```
