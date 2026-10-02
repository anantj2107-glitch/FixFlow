# Backend contract scaffold

Version 1 runs entirely in the browser so it can be reviewed without installing a database or API runtime. This folder defines the next implementation boundary.

## Planned API

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/tickets` | Create a resident request and receive triage suggestions. |
| `GET` | `/api/v1/tickets` | Filter tickets by role, block, status, category, and priority. |
| `PATCH` | `/api/v1/tickets/{ticketId}` | Assign, update, resolve, or reopen a ticket. |
| `POST` | `/api/v1/triage` | Suggest category, urgency, and potential duplicates. |
| `GET` | `/api/v1/analytics/service-health` | Return SLA, workload, and resolution metrics. |

## Data boundary

The production backend will own persistence, authentication, authorization, audit history, attachment uploads, and notifications. The browser must not make final priority or assignment decisions; it only displays the backend's result.

## Suggested implementation

- FastAPI and Pydantic for a documented Python API.
- PostgreSQL for relational ticket data and role access.
- pgvector for duplicate-report embeddings after the ML stage.
- Background worker for notifications and scheduled SLA checks.
