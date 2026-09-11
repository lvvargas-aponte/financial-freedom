"""Settling a month — the advisory handshake between the two instances.

Advisory means: each side publishes its own position, either side may declare a
month paid without the other agreeing, and a disagreement about the net is
reported rather than enforced. These tests pin that down, because the tempting
"both must agree" reading is a different product.
"""
import pytest
from fastapi.testclient import TestClient

import config
import identity_service
import state
from db import identity_repo, period_settlements_repo
from main import app
from sheet_sync import close_together, contract, service, settlement, shared_view
from sheet_sync.gateway import InMemoryGateway

P1, P2 = "Valeria", "Christy"
PEER_ID = "22222222-2222-2222-2222-222222222222"
PERIOD = "2026-06"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def names(monkeypatch):
    monkeypatch.setattr(shared_view, "PERSON_1_NAME", P1)
    monkeypatch.setattr(shared_view, "PERSON_2_NAME", P2)


@pytest.fixture
def peer():
    """The peer with their REAL id.

    Bootstrap already seeded a placeholder in slot 2, so this adopts over it —
    the same call ``service._adopt_peers`` makes when it reads their claim.
    """
    identity_service.ensure_identity()
    identity_repo.adopt_peer_identity(
        person_slot=2, real_user_id=PEER_ID, display_name=P2
    )
    return PEER_ID


def my_row(tid="t1", owes=56.13, **over):
    """A row I paid; the peer owes ``owes``."""
    txn = {
        "date": "06/15/2026", "description": "Groceries", "amount": -112.26,
        "who": P1, "notes": "", "is_shared": True, "reviewed": True,
        "person_1_owes": 0.0, "person_2_owes": owes,
    }
    txn.update(over)
    state.stored_transactions[tid] = txn


def state_of(client):
    return client.get(f"/api/sync/shared-rows?period={PERIOD}").json()["settlement_state"]


class TestStartingPosition:
    def test_a_month_nobody_has_touched_is_open(self, client):
        assert state_of(client)["state"] == "open"

    def test_an_open_month_reports_neither_side_ready(self, client):
        s = state_of(client)
        assert s["you_ready"] is False
        assert s["peer_ready"] is False
        assert s["paid_at"] is None


class TestReady:
    def test_marking_ready_records_the_net_as_it_stands(self, client):
        my_row(owes=56.13)
        body = client.post(f"/api/sync/periods/{PERIOD}/ready").json()

        assert body["settlement_state"]["state"] == "ready"
        assert body["settlement_state"]["you_ready"] is True
        # Positive: the peer owes me.
        assert body["settlement_state"]["declared_net"] == 56.13

    def test_a_net_i_owe_is_recorded_negative(self, client):
        my_row(who=P2, person_1_owes=40.0, person_2_owes=0.0)
        client.post(f"/api/sync/periods/{PERIOD}/ready")

        assert state_of(client)["declared_net"] == -40.0

    def test_withdrawing_ready_returns_the_month_to_open(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/ready")
        body = client.delete(f"/api/sync/periods/{PERIOD}/ready").json()

        assert body["settlement_state"]["state"] == "open"
        assert body["settlement_state"]["declared_net"] is None

    def test_the_declared_net_does_not_move_when_rows_change_afterwards(self, client):
        my_row(owes=56.13)
        client.post(f"/api/sync/periods/{PERIOD}/ready")
        my_row("t2", owes=10.00)

        s = state_of(client)
        assert s["declared_net"] == 56.13
        assert s["live_net"] == 66.13


class TestPaidIsAdvisory:
    def test_either_side_can_mark_paid_without_the_peer_being_ready(self, client, peer):
        my_row()
        body = client.post(f"/api/sync/periods/{PERIOD}/paid").json()

        assert body["settlement_state"]["state"] == "settled"
        assert body["settlement_state"]["paid_by_me"] is True
        assert body["settlement_state"]["peer_ready"] is False

    def test_marking_paid_without_declaring_ready_first_still_works(self, client):
        my_row()
        assert state_of(client)["you_ready"] is False

        client.post(f"/api/sync/periods/{PERIOD}/paid")
        s = state_of(client)
        assert s["state"] == "settled"
        # Paying implies the rows were complete enough to pay against.
        assert s["you_ready"] is True

    def test_the_peer_marking_paid_settles_the_month_here_too(self, client, peer):
        period_settlements_repo.upsert(
            PERIOD, PEER_ID, ready_at="2026-07-01T10:00:00+00:00",
            pif_at="2026-07-01T10:05:00+00:00", pif_note="Venmo",
        )

        s = state_of(client)
        assert s["state"] == "settled"
        assert s["paid_by_me"] is False
        assert s["paid_by_name"] == P2
        assert s["paid_note"] == "Venmo"

    def test_a_note_is_kept_with_the_settlement(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/paid", json={"note": "Zelle, 3 Jul"})

        assert state_of(client)["paid_note"] == "Zelle, 3 Jul"

    def test_a_blank_note_is_stored_as_no_note(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/paid", json={"note": "   "})

        assert state_of(client)["paid_note"] is None


class TestReopen:
    def test_reopening_clears_my_own_settlement(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/paid")
        body = client.delete(f"/api/sync/periods/{PERIOD}/paid").json()

        assert body["settlement_state"]["state"] != "settled"
        assert body["settlement_state"]["paid_at"] is None

    def test_reopening_does_not_clear_the_peers_settlement(self, client, peer):
        period_settlements_repo.upsert(
            PERIOD, PEER_ID, pif_at="2026-07-01T10:05:00+00:00"
        )
        client.post(f"/api/sync/periods/{PERIOD}/paid")

        client.delete(f"/api/sync/periods/{PERIOD}/paid")

        # One-sided in both directions: they said paid, so it stays paid.
        s = state_of(client)
        assert s["state"] == "settled"
        assert s["paid_by_me"] is False


class TestNetDisagreement:
    def test_matching_nets_report_no_disagreement(self, client, peer):
        my_row(owes=56.13)
        client.post(f"/api/sync/periods/{PERIOD}/ready")
        # Their net is signed from their side, so it is ours negated.
        period_settlements_repo.upsert(
            PERIOD, PEER_ID, ready_at="2026-07-01T10:00:00+00:00", net_amount=-56.13
        )

        assert state_of(client)["net_disagreement"] is None

    def test_differing_nets_are_reported_not_resolved(self, client, peer):
        my_row(owes=56.13)
        client.post(f"/api/sync/periods/{PERIOD}/ready")
        period_settlements_repo.upsert(
            PERIOD, PEER_ID, ready_at="2026-07-01T10:00:00+00:00", net_amount=-40.00
        )

        disagreement = state_of(client)["net_disagreement"]
        assert disagreement == {"mine": 56.13, "theirs": 40.00}

    def test_a_disagreement_never_blocks_marking_paid(self, client, peer):
        my_row(owes=56.13)
        client.post(f"/api/sync/periods/{PERIOD}/ready")
        period_settlements_repo.upsert(
            PERIOD, PEER_ID, ready_at="2026-07-01T10:00:00+00:00", net_amount=-40.00
        )

        body = client.post(f"/api/sync/periods/{PERIOD}/paid")
        assert body.status_code == 200
        assert body.json()["settlement_state"]["state"] == "settled"


class TestSyncablePeriods:
    def test_an_unsettled_month_is_swept(self):
        assert PERIOD in service.syncable_periods()

    def test_a_settled_month_drops_out_of_the_sweep(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/paid")

        assert PERIOD not in service.syncable_periods()
        # But the calendar itself is unchanged — it is the work list that shrank.
        assert PERIOD in service.open_periods()

    def test_reopening_puts_it_back_in_the_sweep(self, client):
        my_row()
        client.post(f"/api/sync/periods/{PERIOD}/paid")
        client.delete(f"/api/sync/periods/{PERIOD}/paid")

        assert PERIOD in service.syncable_periods()


def _sheet_row(txn_id, day, owes_1="", owes_2=""):
    headers = contract.build_headers(P1, P2)
    index = contract.header_index_map(headers, P1, P2)
    row = [""] * len(headers)
    row[index["date"]] = day
    row[index["description"]] = "Shared thing"
    row[index["amount"]] = "100"
    row[index["who"]] = P1 if owes_2 else P2
    row[index["owes_1"]] = owes_1
    row[index["owes_2"]] = owes_2
    row[index["txn_id"]] = txn_id
    return row


@pytest.fixture
def sheet(monkeypatch):
    """June: Valeria owes 30. July: Christy owes 100. August: Christy owes 20.

    So June–August nets to Christy paying Valeria 90.
    """
    headers = contract.build_headers(P1, P2)
    gw = InMemoryGateway({
        "June 2026": [headers[:], _sheet_row("a", "06/10/2026", owes_1="30")],
        "July 2026": [headers[:], _sheet_row("b", "07/10/2026", owes_2="100")],
        "August 2026": [headers[:], _sheet_row("c", "08/10/2026", owes_2="20")],
    })
    monkeypatch.setattr(service, "build_gateway", lambda: gw)
    monkeypatch.setattr(config, "PERSON_1_NAME", P1)
    monkeypatch.setattr(config, "PERSON_2_NAME", P2)
    monkeypatch.setattr(close_together, "PERSON_1_NAME", P1)
    monkeypatch.setattr(close_together, "PERSON_2_NAME", P2)
    return gw


def _who_lines(gw, title):
    headers = contract.build_headers(P1, P2)
    who = contract.header_index_map(headers, P1, P2)["who"]
    return [r[who] for r in gw.read_rows(title) if len(r) > who and r[who]]


RUN = {"start": "2026-06", "end": "2026-08"}


class TestCloseTogether:
    def test_preview_nets_the_months_from_the_sheet(self, client, sheet):
        body = client.get("/api/sync/close-together/preview", params=RUN).json()

        assert [m["net"] for m in body["months"]] == [30.0, 100.0, 20.0]
        assert body["months"][0]["debtor"] == P1
        assert body["total"] == {
            "net": 90.0, "debtor": P2, "creditor": P1, "net_for_me": 90.0,
        }
        assert body["label"] == "June–August 2026"
        assert body["blockers"] == []

    def test_preview_flags_a_month_the_app_sees_differently(self, client, sheet):
        my_row("aug", date="08/10/2026", owes=20.0)
        months = client.get("/api/sync/close-together/preview", params=RUN).json()["months"]

        # August matches the app; June and July have no local rows at all.
        assert [m["mismatch"] for m in months] == [True, True, False]

    def test_closing_settles_every_month_as_one_run(self, client, sheet):
        res = client.post("/api/sync/close-together", json={**RUN, "note": "via Zelle"})
        assert res.status_code == 200

        for period in ("2026-06", "2026-07", "2026-08"):
            s = client.get(f"/api/sync/shared-rows?period={period}").json()["settlement_state"]
            assert s["state"] == "settled"
            assert s["closed_together"]["label"] == "June–August 2026"

    def test_every_tab_is_marked_pif(self, client, sheet):
        client.post("/api/sync/close-together", json=RUN)

        assert {"June 2026 - PIF", "July 2026 - PIF", "August 2026 - PIF"} <= set(
            sheet.list_worksheets()
        )

    def test_the_sheet_carries_the_note_and_the_one_payment(self, client, sheet):
        client.post("/api/sync/close-together", json=RUN)

        assert _who_lines(sheet, "June 2026 - PIF")[-1] == (
            "Closed together June–August 2026 · see August 2026"
        )
        assert _who_lines(sheet, "August 2026 - PIF")[-5:] == [
            "Closed together June–August 2026 (aggregated):",
            "June 2026: Valeria owes Christy $30.00",
            "July 2026: Christy owes Valeria $100.00",
            "August 2026: Christy owes Valeria $20.00",
            "Christy pays Valeria via Zelle",
        ]

    def test_a_month_already_paid_refuses_the_whole_run(self, client, sheet, peer):
        period_settlements_repo.upsert(
            "2026-07", PEER_ID, pif_at="2026-08-01T10:00:00+00:00"
        )
        res = client.post("/api/sync/close-together", json=RUN)

        assert res.status_code == 409
        assert "July 2026 is already marked paid in full by Christy" in res.json()["detail"]
        # Nothing was written for the months that could have closed.
        assert settlement.who_settled("2026-06") is None
        assert "June 2026" in sheet.list_worksheets()

    def test_reopening_one_month_reopens_the_run(self, client, sheet):
        client.post("/api/sync/close-together", json=RUN)
        body = client.delete("/api/sync/periods/2026-07/paid").json()

        assert body["reopened"] == ["2026-06", "2026-07", "2026-08"]
        assert settlement.settled_periods() == []
        assert {"June 2026", "July 2026", "August 2026"} <= set(sheet.list_worksheets())
        # Back to an ordinary one-month footer, breakdown gone.
        assert _who_lines(sheet, "August 2026")[-1] == "Christy pays Valeria via Zelle"
        assert not any("Closed together" in line for line in _who_lines(sheet, "August 2026"))

    def test_a_run_before_the_cutover_is_refused(self, client):
        res = client.get(
            "/api/sync/close-together/preview", params={"start": "2026-04", "end": "2026-08"}
        )
        assert res.status_code == 422

    def test_a_run_of_one_month_is_refused(self, client):
        res = client.post(
            "/api/sync/close-together", json={"start": "2026-07", "end": "2026-07"}
        )
        assert res.status_code == 422


class TestPeriodValidation:
    def test_a_month_before_the_cutover_is_refused(self, client):
        assert client.post("/api/sync/periods/2026-01/paid").status_code == 422

    def test_a_malformed_period_is_refused(self, client):
        assert client.post("/api/sync/periods/nonsense/paid").status_code == 422
