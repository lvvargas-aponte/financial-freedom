"""Closing a run of open months with one payment.

Separate from ``settlement.py``: that module is the one-month handshake, and
this one composes it across months — the combined figure, the refusal when any
month in the run cannot be closed, and reopening the run as a unit.

Figures come from the worksheets, not local state: each month's net is what
its own footer prints, the one number both people can check on the sheet. The
app's live figure is reported beside it so a month that has not been synced
shows up before anyone pays against it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import identity_service
from config import PERSON_1_NAME, PERSON_2_NAME
from db import period_settlements_repo
from sheet_sync import contract, footer, service, settlement, shared_view, worksheet


class Blocked(Exception):
    """At least one month in the run cannot be closed."""

    def __init__(self, reasons: List[str]) -> None:
        super().__init__(" ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class _Month:
    period: str
    signed: Decimal            # positive: person 2 owes person 1, as footer signs it
    app_net: Optional[float]   # the app's live figure, from my side


def _group(start: str, end: str) -> str:
    return f"{start}..{end}"


def _for_me(signed: Decimal, my_slot: int) -> Decimal:
    return signed if my_slot == 1 else -signed


def _cents(value: Any) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1")))


def _months(gateway, start: str, end: str) -> tuple[List[_Month], List[str]]:
    """Each month's figures, and every reason the run cannot be closed."""
    months: List[_Month] = []
    blockers: List[str] = []
    for period in worksheet.periods_between(start, end):
        name = worksheet.period_to_title(period)
        if period < worksheet.CUTOVER_PERIOD:
            blockers.append(f"{name} is before the {worksheet.CUTOVER_PERIOD} cutover and is kept by hand.")
            continue

        title = worksheet.find_worksheet(gateway, period)
        if title is None:
            blockers.append(f"{name} has no worksheet yet — sync it first.")
            continue

        settled_by = settlement.who_settled(period)
        if settled_by or worksheet.is_settled_title(title):
            blockers.append(
                f"{name} is already marked paid in full"
                + (f" by {settled_by}." if settled_by else ".")
            )
            continue

        rows = gateway.read_rows(title)
        try:
            index = contract.header_index_map(rows[0] if rows else [], PERSON_1_NAME, PERSON_2_NAME)
        except contract.ContractError:
            blockers.append(f"{title!r} doesn't have the columns sync writes.")
            continue

        owes_1, owes_2 = footer.totals_from_rows(rows, index)
        block = shared_view.shared_rows(period)["settlement"]
        months.append(
            _Month(period=period, signed=owes_2 - owes_1, app_net=settlement.signed_net(block))
        )
    return months, blockers


def _side(signed: Decimal) -> Dict[str, Any]:
    debtor, creditor = footer.debtor_creditor(signed, PERSON_1_NAME, PERSON_2_NAME)
    return {"net": float(abs(signed)), "debtor": debtor, "creditor": creditor}


def preview(start: str, end: str) -> Dict[str, Any]:
    """What closing ``start``..``end`` would settle. Reads only."""
    me = identity_service.ensure_identity()
    months, blockers = _months(service.build_gateway(), start, end)

    rows = []
    for m in months:
        sheet_net = float(_for_me(m.signed, me["person_slot"]))
        rows.append({
            "period": m.period,
            "label": worksheet.period_to_title(m.period),
            **_side(m.signed),
            "sheet_net": sheet_net,
            "app_net": m.app_net,
            "mismatch": m.app_net is not None and _cents(sheet_net) != _cents(m.app_net),
        })

    total = sum((m.signed for m in months), Decimal("0"))
    return {
        "start": start,
        "end": end,
        "label": worksheet.range_label(start, end),
        "months": rows,
        "total": {**_side(total), "net_for_me": float(_for_me(total, me["person_slot"]))},
        "blockers": blockers,
    }


def close(start: str, end: str, note: Optional[str] = None) -> Dict[str, Any]:
    """Mark every month of the run paid by one payment, and write the sheet.

    Records first, then the sheet — ``settlement.publish`` never raises, so a
    sheet failure leaves the local records standing and is reported per month.
    """
    months, blockers = _months(service.build_gateway(), start, end)
    if blockers:
        raise Blocked(blockers)

    group = _group(start, end)
    total = sum((m.signed for m in months), Decimal("0"))
    for m in months:
        settlement.mark_paid(
            m.period, shared_view.shared_rows(m.period)["settlement"],
            note=note, settled_with=group,
        )

    label = worksheet.range_label(start, end)
    summary_title = worksheet.period_to_title(end)
    breakdown = tuple((worksheet.period_to_title(m.period), m.signed) for m in months)
    published = {}
    for m in months:
        is_summary = m.period == end
        closing = footer.Closing(
            label=label,
            summary_title=summary_title,
            months=breakdown if is_summary else (),
            total=total if is_summary else None,
        )
        published[m.period] = settlement.publish(
            m.period, settle=True, method=note, closing=closing
        )

    return {"settled_with": group, "label": label, "total": _side(total), "published": published}


def reopen(period: str) -> Dict[str, Dict[str, Any]]:
    """Undo my "paid in full" on ``period`` — and on every month closed with it.

    One payment covered the whole run, so reopening one month of it reopens
    them all; each returns to an ordinary one-month footer.
    """
    me = identity_service.ensure_identity()
    mine = period_settlements_repo.get(period, me["user_id"]) or {}
    periods = settlement.group_periods(mine.get("settled_with")) or [period]

    published = {}
    for p in periods:
        settlement.reopen(p)
        published[p] = settlement.publish(p)
    return published
