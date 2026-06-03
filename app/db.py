import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.settings import settings

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False)

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def _split_statements(sql: str) -> list[str]:
    """Split a SQL script into individual statements.

    asyncpg runs every statement through the extended (prepared) protocol,
    which rejects multiple commands in one call. We split on ';' — safe here
    because our migrations contain no semicolons inside string literals.
    """
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]


async def run_migrations() -> None:
    """Execute all SQL migration files in order against the connected DB."""
    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    async with engine.begin() as conn:
        for sql_file in sql_files:
            sql = sql_file.read_text(encoding="utf-8")
            for statement in _split_statements(sql):
                await conn.execute(text(statement))


if __name__ == "__main__":
    asyncio.run(run_migrations())
