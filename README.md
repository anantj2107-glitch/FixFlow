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
- Triage: transparent priority rules and private possible-duplicate suggestions.
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
.\.venv\Scripts\python.exe -m unittest tests.test_auth_rbac tests.test_duplicate_detection tests.test_issue_recommendation
```

To restore the supplied demo data during development, stop the server and delete `backend/fixflow.db`; starting the server again will seed the sample tickets.

## Phase 3 Part 1: multilingual duplicate suggestions

When a resident submits a report, FixFlow normalizes harmless punctuation, case,
whitespace, and a small, documented set of common Hinglish maintenance terms. It
then considers only unresolved tickets in the same category, scores description
similarity plus block and room signals, and returns at most three ranked
suggestions. It never merges, blocks, or rejects a report.

The preferred engine is the optional local
`paraphrase-multilingual-MiniLM-L12-v2` sentence-embedding model. It loads only
when first needed and caches embeddings in the running process. Install it only
on machines able to download and run the model:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-ml.txt
```

Without that optional package, during model download/load failure, or on an
embedding failure, FixFlow stays available and uses a transparent lexical
similarity fallback. The API response and resident UI label this as `lexical_fallback`;
it is not presented as semantic AI.

Optional controls in `.env`:

```text
DUPLICATE_SIMILARITY_THRESHOLD=0.62
DUPLICATE_EMBEDDINGS_ENABLED=true
```

Scores are ranking signals, not probabilities or accuracy claims. The small
normalization map cannot cover every language, spelling, or local phrase. Model
quality needs evaluation on reviewed hostel reports before any operational claim.

For privacy, suggestions are sent only in the response to the resident's newly
created ticket. They contain only ticket ID, score, method, and a generic reason;
they never expose another resident's description, name, room, or identity. Ticket
listing ownership and staff RBAC rules remain server enforced.

## Phase 3 Part 2: category and urgency guidance

FixFlow now provides guidance while a resident types a report. The backend accepts
only FixFlow's existing categories: `Plumbing`, `Electricity`, `Lift`,
`Cleaning`, `Security`, `Internet`, `Furniture`, and `Other`. The resident's
selection stays in control. A different recommendation has an explicit **Use
category** button; FixFlow never changes the selection automatically.

Category guidance starts with a transparent, manually maintained maintenance
vocabulary for English, Devanagari Hindi, and common Hinglish. It is an offline
keyword-profile baseline, not a trained classifier. If the optional Part 1
sentence-transformer dependency is installed, the already cached local model can
also compare text with those manual profiles. The response identifies the method
as `keyword_rules`, `embedding_profile`, `selected_category_fallback`, or
`unknown_fallback`.

Priority advice is deterministic. Fire, smoke, gas leaks, electric shock/live
wires, sparking, flooding, immediate danger, and stuck-lift language produce a
High safety recommendation. Other priorities follow the existing category
baseline. Embeddings never override a safety rule. Staff can still reprioritize
work during triage.

The displayed confidence is a local ranking signal, not a probability or a
model-accuracy claim. No labelled operational dataset exists in this repository,
so FixFlow reports no category or urgency metric. The focused tests are the
reproducible baseline evaluation for known examples:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_auth_rbac tests.test_duplicate_detection tests.test_issue_recommendation
```

Known limits: keyword coverage is incomplete, Hindi/Hinglish phrasing varies,
and manual profiles can misclassify ambiguous text. Use staff review for all
workflow decisions, especially safety reports.

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
3. Local multilingual sentence embeddings for duplicate suggestions (available in Phase 3 fallback-first form).
4. Small supervised category classifier only after collecting reviewed labelled hostel reports.
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
  backend/app/duplicate_detection.py # Optional embedding and lexical duplicate service
  backend/app/text_normalization.py # Explainable maintenance-text normalization
  backend/app/issue_recommendation.py # Offline category and priority guidance
  backend/app/create_user.py # Local-only technician/warden/admin bootstrap
  backend/requirements-ml.txt # Optional multilingual embedding dependency
  tests/test_issue_recommendation.py # Deterministic Part 2 evaluation cases
  .env.example            # Required environment keys; no secrets
  backend/fixflow.db      # Local data, created on first server start
  ml/                     # Data, evaluation, and model roadmap
  docs/                   # Product delivery roadmap
  README.md               # Architecture and run guide
```
