# FixFlow — Multilingual Hostel Maintenance Intelligence Platform

FixFlow helps hostel residents report maintenance issues and gives operations teams a clear queue for assignment and resolution.

## Version 1: working now

Version 2 is a responsive web application served by FastAPI. Tickets persist in a local SQLite database at `backend/fixflow.db`.

- Resident: submit and track a maintenance request.
- Operations: review, filter, assign, resolve, or reopen requests.
- Technician: see active assigned work and resolve it.
- Triage: transparent priority rules plus persisted same-category/same-block duplicate flags.
- Responsive UI: works on desktop and mobile browser sizes.

## Run locally

From this folder in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

API documentation is available at `http://127.0.0.1:8000/docs`.

Run the backend smoke test with:

```powershell
.\.venv\Scripts\python.exe tests\test_backend_smoke.py
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

1. Authentication and role-based access for resident, warden, admin, technician.
2. FastAPI endpoints and PostgreSQL persistence.
3. Image attachments with secure storage.
4. Local multilingual sentence embeddings for duplicate detection.
5. Small supervised category classifier trained on labelled hostel reports.
6. Notifications, activity history, SLA policies, and analytics.

## Practical ML plan

Start with 300–600 reviewed reports in 6–8 categories. Keep a test set that is never used for training. Report category macro-F1 and duplicate-match precision. The product remains useful even when the model is uncertain: it can show a suggested category and let staff correct it.

## Repository layout

```text
FixFlow/
  index.html              # Responsive application shell
  css/styles.css          # Responsive design system
  js/data.js              # Browser configuration and categories
  js/app.js               # API-connected views and workflow
  backend/app/main.py     # FastAPI routes, SQLite persistence, static hosting
  backend/fixflow.db      # Local data, created on first server start
  ml/                     # Data, evaluation, and model roadmap
  docs/                   # Product delivery roadmap
  README.md               # Architecture and run guide
```
