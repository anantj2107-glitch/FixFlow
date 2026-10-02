from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "backend" / "fixflow.db"
STATUSES = {"Open", "In progress", "Resolved"}
PRIORITIES = {"High", "Medium", "Low"}
DEMO_TICKETS = [
    ("FF-1042", "Plumbing", "A", "204", "Water is leaking continuously below the washroom sink.", "High", "Open", "Unassigned", "Aarav Kumar", "Today, 10:12"),
    ("FF-1041", "Lift", "B", "Lobby", "Lift 2 is stuck on the third floor and is not responding.", "High", "In progress", "Rohan Singh", "Meera Shah", "Today, 09:38"),
    ("FF-1040", "Electricity", "A", "118", "The tube light near my desk keeps flickering.", "Medium", "Open", "Unassigned", "Aarav Kumar", "Yesterday, 21:03"),
    ("FF-1039", "Internet", "C", "306", "Wi-Fi has been unavailable in our room since evening.", "Medium", "In progress", "Priya Nair", "Kabir Jain", "Yesterday, 18:20"),
    ("FF-1038", "Cleaning", "A", "Common area", "Waste has not been collected from the pantry.", "Low", "Resolved", "Anil Das", "Aarav Kumar", "Yesterday, 12:14"),
]


@contextmanager
def connection():
    database = sqlite3.connect(DATABASE_PATH)
    database.row_factory = sqlite3.Row
    try:
        yield database
        database.commit()
    finally:
        database.close()


def initialize_database() -> None:
    with connection() as database:
        database.execute("""CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, category TEXT NOT NULL, block TEXT NOT NULL, room TEXT NOT NULL, description TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, assignee TEXT NOT NULL, resident TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        if database.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == 0:
            now = datetime.now(timezone.utc).isoformat()
            database.executemany("INSERT INTO tickets (id, category, block, room, description, priority, status, assignee, resident, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [(*ticket, now) for ticket in DEMO_TICKETS])


def find_duplicate(ticket: dict, ignore_id: str | None = None) -> str | None:
    with connection() as database:
        row = database.execute("SELECT id FROM tickets WHERE category = ? AND block = ? AND status != 'Resolved' AND id != ? ORDER BY updated_at DESC LIMIT 1", (ticket["category"], ticket["block"], ignore_id or "")).fetchone()
    return row["id"] if row else None


def ticket_dictionary(row: sqlite3.Row) -> dict:
    ticket = dict(row)
    ticket["duplicate_of"] = find_duplicate(ticket, ticket["id"])
    return ticket


def infer_priority(category: str, description: str) -> str:
    urgent_terms = ("fire", "smoke", "sparking", "electric shock", "gas leak", "stuck", "flood", "security", "danger", "emergency")
    if category == "Security" or any(term in description.lower() for term in urgent_terms):
        return "High"
    return "Medium" if category in {"Electricity", "Lift", "Plumbing", "Internet"} else "Low"


def next_ticket_id(database: sqlite3.Connection) -> str:
    latest = database.execute("SELECT id FROM tickets ORDER BY CAST(SUBSTR(id, 4) AS INTEGER) DESC LIMIT 1").fetchone()
    return f"FF-{int(latest['id'].split('-')[1]) + 1 if latest else 1001}"


class TicketCreate(BaseModel):
    category: str = Field(min_length=2, max_length=50)
    block: str = Field(min_length=1, max_length=30)
    room: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=8, max_length=1200)
    resident: str = Field(min_length=2, max_length=80)


class TicketUpdate(BaseModel):
    status: Literal["Open", "In progress", "Resolved"] | None = None
    assignee: str | None = Field(default=None, min_length=2, max_length=80)


initialize_database()
app = FastAPI(title="FixFlow API", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "fixflow-api", "version": "0.2.0"}


@app.get("/api/v1/tickets")
def list_tickets(status: str | None = Query(default=None), priority: str | None = Query(default=None), resident: str | None = Query(default=None)) -> list[dict]:
    query, parameters = "SELECT * FROM tickets WHERE 1 = 1", []
    if status:
        if status not in STATUSES: raise HTTPException(status_code=422, detail="Unknown status")
        query, parameters = query + " AND status = ?", [*parameters, status]
    if priority:
        if priority not in PRIORITIES: raise HTTPException(status_code=422, detail="Unknown priority")
        query, parameters = query + " AND priority = ?", [*parameters, priority]
    if resident:
        query, parameters = query + " AND resident = ?", [*parameters, resident]
    query += " ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, updated_at DESC"
    with connection() as database:
        rows = database.execute(query, parameters).fetchall()
    return [ticket_dictionary(row) for row in rows]


@app.post("/api/v1/tickets", status_code=201)
def create_ticket(payload: TicketCreate) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with connection() as database:
        ticket_id = next_ticket_id(database)
        database.execute("INSERT INTO tickets (id, category, block, room, description, priority, status, assignee, resident, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'Open', 'Unassigned', ?, ?, ?)", (ticket_id, payload.category, payload.block, payload.room, payload.description, infer_priority(payload.category, payload.description), payload.resident, "Just now", now))
        row = database.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return ticket_dictionary(row)


@app.patch("/api/v1/tickets/{ticket_id}")
def update_ticket(ticket_id: str, payload: TicketUpdate) -> dict:
    fields = payload.model_dump(exclude_none=True)
    if not fields: raise HTTPException(status_code=422, detail="Provide at least one update")
    with connection() as database:
        if not database.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone(): raise HTTPException(status_code=404, detail="Ticket not found")
        assignments = ", ".join(f"{field} = ?" for field in fields)
        database.execute(f"UPDATE tickets SET {assignments}, updated_at = ? WHERE id = ?", [*fields.values(), datetime.now(timezone.utc).isoformat(), ticket_id])
        row = database.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    return ticket_dictionary(row)


@app.get("/api/v1/analytics/service-health")
def service_health() -> dict:
    with connection() as database: tickets = [dict(row) for row in database.execute("SELECT status, priority, assignee FROM tickets").fetchall()]
    active = [ticket for ticket in tickets if ticket["status"] != "Resolved"]
    return {"open": sum(ticket["status"] == "Open" for ticket in tickets), "in_progress": sum(ticket["status"] == "In progress" for ticket in tickets), "resolved": sum(ticket["status"] == "Resolved" for ticket in tickets), "high_priority": sum(ticket["priority"] == "High" and ticket["status"] != "Resolved" for ticket in tickets), "unassigned": sum(ticket["assignee"] == "Unassigned" and ticket["status"] != "Resolved" for ticket in tickets), "active": len(active)}


app.mount("/", StaticFiles(directory=str(PROJECT_ROOT), html=True), name="web")
