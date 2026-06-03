"""Standalone migration runner: python -m migrations.run"""

import asyncio

from app.db import run_migrations

if __name__ == "__main__":
    asyncio.run(run_migrations())
