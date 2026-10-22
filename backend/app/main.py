from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, EmailStr, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()
DATABASE_PATH = Path(os.environ.get("FIXFLOW_DATABASE_PATH", PROJECT_ROOT / "backend" / "fixflow.db"))
JWT_SECRET = os.environ.get("JWT_SECRET")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "60"))
JWT_ALGORITHM = "HS256"
STATUSES = {"Open", "In progress", "Resolved"}
PRIORITIES = {"High", "Medium", "Low"}
ROLES = {"resident", "technician", "warden", "admin"}
STAFF_ROLES = {"warden", "admin"}
password_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)

DEMO_TICKETS = [
    ("FF-1042", "Plumbing", "A", "204", "Water is leaking continuously below the washroom sink.", "High", "Open", "Unassigned", "Aarav Kumar", "Today, 10:12"),
    ("FF-1041", "Lift", "B", "Lobby", "Lift 2 is stuck on the third floor and is not responding.", "High", "In progress", "Rohan Singh", "Meera Shah", "Today, 09:38"),
    ("FF-1040", "Electricity", "A", "118", "The tube light near my desk keeps flickering.", "Medium", "Open", "Unassigned", "Aarav Kumar", "Yesterday, 21:03"),
    ("FF-1039", "Internet", "C", "306", "Wi-Fi has been unavailable in our room since evening.", "Medium", "In progress", "Priya Nair", "Kabir Jain", "Yesterday, 18:20"),
    ("FF-1038", "Cleaning", "A", "Common area", "Waste has not been collected from the pantry.", "Low", "Resolved", "Anil Das", "Aarav Kumar", "Yesterday, 12:14"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def require_jwt_secret() -> str:
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET missing or too short. Add a 32+ character value to .env.")
    return JWT_SECRET


@contextmanager
def connection():
    database = sqlite3.connect(DATABASE_PATH)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    try:
        yield database
        database.commit()
    finally:
        database.close()


def column_exists(database: sqlite3.Connection, table: str, column: str) -> bool:
    return column in {row["name"] for row in database.execute(f"PRAGMA table_info({table})").fetchall()}


def initialize_database() -> None:
    require_jwt_secret()
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as database:
        database.execute("""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE COLLATE NOCASE, display_name TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('resident', 'technician', 'warden', 'admin')), created_at TEXT NOT NULL)""")
        database.execute("""CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, category TEXT NOT NULL, block TEXT NOT NULL, room TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, assignee TEXT NOT NULL, resident TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        if not column_exists(database, "tickets", "resident_id"):
            database.execute("ALTER TABLE tickets ADD COLUMN resident_id INTEGER REFERENCES users(id)")
        if not column_exists(database, "tickets", "assigned_to_id"):
            database.execute("ALTER TABLE tickets ADD COLUMN assigned_to_id INTEGER REFERENCES users(id)")
        if database.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            now = utc_now()
            database.executemany("INSERT INTO tickets (id, category, block, room, description, priority, status, assignee, resident, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(*ticket, now) for ticket in DEMO_TICKETS])


def user_dictionary(row: sqlite3.Row) -> dict:
    return {"id": row["id"], "email": row["email"], "display_name": row["display_name"], "role": row["role"]}


def create_user_record(email: str, display_name: str, password: str, role: str) -> dict:
    if role not in ROLES:
        raise ValueError("Invalid role")
    if len(password) < 10:
        raise ValueError("Password must contain at least 10 characters")
    try:
        with connection() as database:
            cursor = database.execute("INSERT INTO users (email, display_name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)", (email.lower().strip(), display_name.strip(), password_hasher.hash(password), role, utc_now()))
            row = database.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as error:
        raise ValueError("Email already registered") from error
    return user_dictionary(row)


def read_ticket(database: sqlite3.Connection, ticket_id: str) -> sqlite3.Row | None:
    return database.execute("""SELECT tickets.*, residents.display_name AS resident_name, assignees.display_name AS assignee_name FROM tickets LEFT JOIN users AS residents ON residents.id = tickets.resident_id LEFT JOIN users AS assignees ON assignees.id = tickets.assigned_to_id WHERE tickets.id = ?""", (ticket_id,)).fetchone()


def find_duplicate(ticket: dict, ignore_id: str | None = None) -> str | None:
    with connection() as database:
        row = database.execute("SELECT id FROM tickets WHERE category = ? AND block = ? AND status != 'Resolved' AND id != ? ORDER BY updated_at DESC LIMIT 1", (ticket["category"], ticket["block"], ignore_id or "")).fetchone()
    return row["id"] if row else None


def ticket_dictionary(row: sqlite3.Row) -> dict:
    ticket = dict(row)
    ticket["resident"] = ticket.pop("resident_name") or ticket["resident"]
    ticket["assignee"] = ticket.pop("assignee_name") or ticket["assignee"]
    ticket["duplicate_of"] = find_duplicate(ticket, ticket["id"])
    return ticket


def infer_priority(category: str, description: str) -> str:
    terms = ("fire", "smoke", "sparking", "electric shock", "gas leak", "stuck", "flood", "security", "danger", "emergency")
    if category == "Security" or any(term in description.lower() for term in terms):
        return "High"
    return "Medium" if category in {"Electricity", "Lift", "Plumbing", "Internet"} else "Low"


def next_ticket_id(database: sqlite3.Connection) -> str:
    latest = database.execute("SELECT id FROM tickets ORDER BY CAST(SUBSTR(id, 4) AS INTEGER) DESC LIMIT 1").fetchone()
    return f"FF-{int(latest['id'].split('-')[1]) + 1 if latest else 1001}"


class PublicRegistration(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    display_name: str
    role: Literal["resident", "technician", "warden", "admin"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    category: str = Field(min_length=2, max_length=50)
    block: str = Field(min_length=1, max_length=30)
    room: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=8, max_length=1200)


class TicketUpdate(BaseModel):
    status: Literal["Open", "In progress", "Resolved"] | None = None
    assignee_id: int | None = Field(default=None, gt=0)


def create_access_token(user: dict) -> tuple[str, int]:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    token = jwt.encode({"sub": str(user["id"]), "role": user["role"], "exp": expires_at}, require_jwt_secret(), algorithm=JWT_ALGORITHM)
    return token, JWT_EXPIRE_MINUTES * 60


def unauthenticated(message: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message, headers={"WWW-Authenticate": "Bearer"})


def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]) -> dict:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise unauthenticated()
    try:
        payload = jwt.decode(credentials.credentials, require_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub", ""))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise unauthenticated("Invalid or expired access token")
    with connection() as database:
        row = database.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise unauthenticated("Account no longer exists")
    return user_dictionary(row)


def require_roles(*allowed_roles: str):
    def dependency(user: Annotated[dict, Depends(current_user)]) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency


initialize_database()
app = FastAPI(title="FixFlow API", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "fixflow-api", "version": "0.3.0"}


@app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: PublicRegistration) -> TokenResponse:
    try:
        user = create_user_record(str(payload.email), payload.display_name, payload.password, "resident")
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    with connection() as database:
        row = database.execute("SELECT * FROM users WHERE email = ?", (str(payload.email).lower(),)).fetchone()
    if not row:
        raise unauthenticated("Invalid email or password")
    try:
        password_hasher.verify(row["password_hash"], payload.password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        raise unauthenticated("Invalid email or password")
    user = user_dictionary(row)
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=user)


@app.get("/api/v1/auth/me", response_model=UserResponse)
def me(user: Annotated[dict, Depends(current_user)]) -> UserResponse:
    return UserResponse(**user)


@app.get("/api/v1/users/technicians", response_model=list[UserResponse])
def technicians(_: Annotated[dict, Depends(require_roles("warden", "admin"))]) -> list[UserResponse]:
    with connection() as database:
        rows = database.execute("SELECT * FROM users WHERE role = 'technician' ORDER BY display_name").fetchall()
    return [UserResponse(**user_dictionary(row)) for row in rows]


@app.get("/api/v1/tickets")
def list_tickets(user: Annotated[dict, Depends(current_user)], status_filter: str | None = Query(default=None, alias="status"), priority: str | None = Query(default=None, alias="priority")) -> list[dict]:
    if status_filter and status_filter not in STATUSES:
        raise HTTPException(status_code=422, detail="Unknown status")
    if priority and priority not in PRIORITIES:
        raise HTTPException(status_code=422, detail="Unknown priority")
    query, parameters = """SELECT tickets.*, residents.display_name AS resident_name, assignees.display_name AS assignee_name FROM tickets LEFT JOIN users AS residents ON residents.id = tickets.resident_id LEFT JOIN users AS assignees ON assignees.id = tickets.assigned_to_id WHERE 1 = 1""", []
    if user["role"] == "resident":
        query, parameters = query + " AND tickets.resident_id = ?", [*parameters, user["id"]]
    elif user["role"] == "technician":
        query, parameters = query + " AND tickets.assigned_to_id = ?", [*parameters, user["id"]]
    if status_filter:
        query, parameters = query + " AND tickets.status = ?", [*parameters, status_filter]
    if priority:
        query, parameters = query + " AND tickets.priority = ?", [*parameters, priority]
    query += " ORDER BY CASE tickets.priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, tickets.updated_at DESC"
    with connection() as database:
        rows = database.execute(query, parameters).fetchall()
    return [ticket_dictionary(row) for row in rows]


@app.post("/api/v1/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, user: Annotated[dict, Depends(require_roles("resident"))]) -> dict:
    with connection() as database:
        ticket_id = next_ticket_id(database)
        now = utc_now()
        database.execute("INSERT INTO tickets (id, category, block, room, description, priority, status, assignee, resident, resident_id, assigned_to_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'Open', 'Unassigned', ?, ?, NULL, 'Just now', ?)", (ticket_id, payload.category, payload.block, payload.room, payload.description, infer_priority(payload.category, payload.description), user["display_name"], user["id"], now))
        row = read_ticket(database, ticket_id)
    return ticket_dictionary(row)


@app.patch("/api/v1/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: TicketUpdate, user: Annotated[dict, Depends(current_user)]) -> dict:
    fields = payload.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=422, detail="Provide at least one update")
    with connection() as database:
        ticket = read_ticket(database, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        if user["role"] == "resident":
            raise HTTPException(status_code=403, detail="Residents cannot update ticket workflow")
        if user["role"] == "technician":
            if ticket["assigned_to_id"] != user["id"]:
                raise HTTPException(status_code=403, detail="Ticket is not assigned to you")
            if "assignee_id" in fields or fields.get("status") not in {"In progress", "Resolved"}:
                raise HTTPException(status_code=403, detail="Technicians can only update assigned ticket status")
        if "assignee_id" in fields:
            assignee = database.execute("SELECT * FROM users WHERE id = ?", (fields["assignee_id"],)).fetchone()
            if not assignee or assignee["role"] != "technician":
                raise HTTPException(status_code=422, detail="Assignee must be an existing technician")
            fields["assigned_to_id"] = fields.pop("assignee_id")
            fields["assignee"] = assignee["display_name"]
        assignments = ", ".join(f"{field} = ?" for field in fields)
        database.execute(f"UPDATE tickets SET {assignments}, updated_at = ? WHERE id = ?", [*fields.values(), utc_now(), ticket_id])
        updated = read_ticket(database, ticket_id)
    return ticket_dictionary(updated)


@app.get("/api/v1/analytics/service-health")
def service_health(_: Annotated[dict, Depends(require_roles("warden", "admin"))]) -> dict:
    with connection() as database:
        tickets = [dict(row) for row in database.execute("SELECT status, priority, assignee FROM tickets").fetchall()]
    active = [ticket for ticket in tickets if ticket["status"] != "Resolved"]
    return {"open": sum(ticket["status"] == "Open" for ticket in tickets), "in_progress": sum(ticket["status"] == "In progress" for ticket in tickets), "resolved": sum(ticket["status"] == "Resolved" for ticket in tickets), "high_priority": sum(ticket["priority"] == "High" and ticket["status"] != "Resolved" for ticket in tickets), "unassigned": sum(ticket["assignee"] == "Unassigned" and ticket["status"] != "Resolved" for ticket in tickets), "active": len(active)}


app.mount("/", StaticFiles(directory=str(PROJECT_ROOT), html=True), name="web")
