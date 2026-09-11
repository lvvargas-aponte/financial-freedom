"""A SimpleFIN sync reports which transactions it added.

The Current page uses those ids to offer categories for exactly what the sync
brought in, so a re-sync of rows already stored must report none.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import state
from main import app
from routers import simplefin as simplefin_router

WINDOW = {"from_date": "2026-08-01", "to_date": "2026-08-31"}


def _posted(day: str) -> int:
    return int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


ACCOUNT = {
    "id": "acct-1",
    "_org_name": "Bank",
    "name": "Checking",
    "transactions": [
        {"id": "sf-1", "posted": _posted("2026-08-15"), "amount": "-12.50", "description": "COFFEE"},
        {"id": "sf-2", "posted": _posted("2026-08-16"), "amount": "-40.00", "description": "GROCER"},
    ],
}


@pytest.fixture
def client(monkeypatch):
    async def accounts(_start, _end):
        return [("https://bridge.example", [ACCOUNT])], []

    async def no_balances(*_args, **_kwargs):
        return None

    monkeypatch.setattr(state, "SIMPLEFIN_ACCESS_URLS", ["https://bridge.example"])
    monkeypatch.setattr(state.simplefin, "list_accounts_by_url", accounts)
    monkeypatch.setattr(simplefin_router, "persist_simplefin_balances", no_balances)
    return TestClient(app)


def test_a_sync_lists_the_transactions_it_added(client):
    body = client.post("/api/simplefin/sync", json=WINDOW).json()

    assert body["total_new"] == 2
    assert sorted(body["new_ids"]) == ["sf-1", "sf-2"]


def test_a_resync_adds_nothing_and_lists_nothing(client):
    client.post("/api/simplefin/sync", json=WINDOW)
    body = client.post("/api/simplefin/sync", json=WINDOW).json()

    assert body["total_new"] == 0
    assert body["new_ids"] == []
