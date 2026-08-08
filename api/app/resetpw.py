"""Set a password from the host, for when nobody can get in.

    docker compose exec api python -m app.resetpw you@example.com

There is no reset email, and there shouldn't be: this is somebody's own
server, and requiring an SMTP host before you can recover your own account
would be a worse problem than the one it solves. Whoever can reach the
container can already read the database, so shell access is the credential.

Run with no arguments to list the accounts, or --clear to take the lock off a
single-user install entirely.
"""

import getpass
import sys

from app.auth import hash_password
from app.db import SessionLocal
from app.models import User


def main() -> int:
    args = [a for a in sys.argv[1:] if a]
    with SessionLocal() as db:
        if args and args[0] in ("--clear", "-c"):
            # the way back in when somebody locks themselves out of a
            # one-account install: no password means no login screen, which is
            # where this app started
            owner = db.get(User, 1)
            if owner is None:
                print("No owner account.", file=sys.stderr)
                return 1
            owner.password_hash = None
            db.commit()
            print("Password cleared — this install no longer asks for one.")
            return 0

        if not args:
            users = db.query(User).order_by(User.id).all()
            print(f"{len(users)} account(s):")
            for u in users:
                who = u.email or "(no email set)"
                mark = " admin" if u.is_admin else ""
                pw = "" if u.password_hash else "  — no password set"
                print(f"  {u.id}. {who}{mark}{pw}")
            print("\nUsage: python -m app.resetpw <email>")
            return 0

        email = args[0].strip()
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            # The owner exists before it has an email — that's the state a
            # single-user install lives in — so offer to name it rather than
            # refusing on a technicality.
            owner = db.get(User, 1)
            if owner is not None and owner.email is None:
                print(f"No account for {email}. Setting it on the owner account (id 1).")
                owner.email = email
                user = owner
            else:
                print(f"No account for {email}.", file=sys.stderr)
                return 1

        first = getpass.getpass("New password (8+ characters): ")
        if len(first) < 8:
            print("Too short.", file=sys.stderr)
            return 1
        if first != getpass.getpass("Again: "):
            print("They don't match.", file=sys.stderr)
            return 1

        user.password_hash = hash_password(first)
        db.commit()
        print(f"Password set for {user.email}.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
