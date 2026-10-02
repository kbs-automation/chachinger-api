"""Create an admin user, or promote an existing user to admin.

Usage: python -m scripts.create_admin admin@example.com
The password is read interactively so it never lands in shell history.
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import User
from app.services.auth import generate_player_number


async def create_admin(email: str, password: str) -> None:
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            user = User(
                email=email.lower(),
                password_hash=hash_password(password),
                player_number=await generate_player_number(db),
                username=None,
                is_admin=True,
            )
            db.add(user)
            action = "created"
        else:
            user.is_admin = True
            user.password_hash = hash_password(password)
            action = "promoted"
        await db.commit()
    await engine.dispose()
    print(f"Admin {action}: {email}")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m scripts.create_admin <email>")
    password = getpass.getpass("Admin password: ")
    if len(password) < 12:
        sys.exit("Admin password must be at least 12 characters")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match")
    asyncio.run(create_admin(sys.argv[1], password))


if __name__ == "__main__":
    main()
