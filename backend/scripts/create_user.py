"""Create the first admin or another application user without exposing a web bootstrap route."""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import SessionLocal  # noqa: E402
from services.auth import create_user  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Create a SAJAG user")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--sites", default="*", help="Comma-separated site names; use * only for unrestricted accounts")
    args = parser.parse_args()
    password = getpass.getpass("Password (minimum 10 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    db = SessionLocal()
    try:
        user = create_user(
            db, name=args.name, email=args.email, username=args.username, password=password,
            role=args.role, site_scope=[site.strip() for site in args.sites.split(",") if site.strip()],
        )
        db.commit()
        print(f"Created {user.username} ({user.role}) with user id {user.user_id}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
