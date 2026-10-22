"""Local-only privileged account bootstrap. Never expose this through HTTP."""

import argparse
import getpass

from backend.app.main import create_user_record, initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a local FixFlow staff account")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True, choices=("technician", "warden", "admin"))
    arguments = parser.parse_args()
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    initialize_database()
    user = create_user_record(arguments.email, arguments.name, password, arguments.role)
    print(f"Created {user['role']} account for {user['email']}")


if __name__ == "__main__":
    main()
