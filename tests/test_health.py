import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5433/cortex")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

from app.main import app  # noqa: E402


@pytest.mark.integration
async def test_health_endpoint() -> None:
    """Requires running Postgres. Verifies DB connectivity end-to-end."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["db"] == "connected"
