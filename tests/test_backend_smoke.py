"""Dependency-free smoke test for FixFlow's API domain functions."""

import tempfile
from pathlib import Path

from backend.app import main


def run() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        main.DATABASE_PATH = Path(temporary_directory) / "fixflow-test.db"
        main.initialize_database()

        created = main.create_ticket(
            main.TicketCreate(
                category="Plumbing",
                block="A",
                room="211",
                resident="Test Resident",
                description="Paani leak ho raha hai below the washroom sink.",
            )
        )
        assert created["status"] == "Open"
        assert created["priority"] == "Medium"
        assert created["duplicate_of"] == "FF-1042"

        assigned = main.update_ticket(created["id"], main.TicketUpdate(status="In progress", assignee="Rohan Singh"))
        assert assigned["status"] == "In progress"
        assert assigned["assignee"] == "Rohan Singh"

        resolved = main.update_ticket(created["id"], main.TicketUpdate(status="Resolved"))
        assert resolved["status"] == "Resolved"
        assert main.service_health()["resolved"] == 2

    print("FixFlow backend smoke test: PASS")


if __name__ == "__main__":
    run()
