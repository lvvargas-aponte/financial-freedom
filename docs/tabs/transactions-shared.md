# Transactions → Shared

> Source: `frontend/src/components/shared/*`, `backend/routers/sync.py`, `backend/gsheet_integration.py`

The settle-up view for a two-person household. Where [Current](transactions-current.md) is where you
*mark* a transaction as shared, Shared is where the two sides reconcile a month and agree it is paid.

The Google Sheet is the shared record between the two installs — each side pushes its own rows and
pulls the other's.

## Month picker

One month at a time, chosen from the header. The list starts at the cutover period (`2026-06`) — the
first month this flow covered — and runs to the current month.

## Settle up

The card at the top states the month's position: what each person paid, what each owes, and the net
figure one owes the other.

**Only rows with a split are counted.** A row marked shared but with no split amounts is not in the
total — it shows in the attention strip instead.

### Settlement states

| Action | Meaning |
|---|---|
| **Mark ready** | Your side's rows for the month are final. Withdrawable until the other side acts. |
| **Mark paid** | The transfer happened. Takes an optional note. |
| **Reopen** | Puts a settled month back in play. |

Every settlement call returns the month's whole recomputed position, so the card updates from the
response rather than a second round trip. If the other side settles first, their record wins — the
page reloads rather than showing a state that lost.

### Close several months together

When more than one month is open, **Close several months…** in the header pays them all off with one
transfer:

1. Pick the first and last month and click **Preview**. Each month shows who owes whom, taken from
   that month's tab. A month where the app has a different figure is flagged — sync it before closing.
2. The preview adds the months up into one line: who pays whom, and how much in total.
3. Add an optional note and click **Close N months**.

Every month in the range is marked paid and its tab gets the ` - PIF` suffix. Each tab keeps its own
totals, and its payment line reads *Closed together June–August 2026 · see August 2026*. The last
month's tab lists each month's figure and the one payment line for the total.

The whole range is refused if any month in it is already paid, has no tab yet, or is before the
`2026-06` cutover. **Reopen** on any of those months reopens all of them, and each tab goes back to
an ordinary one-month footer.

## Sync now

**Sync now** pushes your shared rows to the sheet and pulls the peer's. The result line reports
`N sent, M received` plus any disputes sent.

Two outcomes are not errors and read differently:

- **Refused** — the sync was declined with a reason (for example, the period is already settled).
- **Error** — the sheet could not be reached or written.

Both leave your local rows untouched and reload the month.

## Attention strip

Rows that need something before they can count:

- **Missing split** — marked shared, but nobody's share is set.
- **Missing who** — the payer slot is blank. Repairable inline from a picker of the two configured
  person names (`GET /api/config/person-names`).

Clicking through filters the list to just those rows.

## Corrections feed

When the peer edits a row you had already synced, it arrives as a correction rather than silently
overwriting yours. Each entry can be dismissed once you have looked at it.

## Disputes

Any row can be disputed — you disagree with the split, the amount, or that it is shared at all. The
dispute rides along on the next sync and shows on the peer's side.

## The list

Rows grouped by date, newest first, with a filter above (all / attention / yours / theirs). A colour
key marks who paid.

## Under the hood

- `GET /api/sync/shared-rows?period=YYYY-MM` — the month's rows, settlement and peer identity
- `GET /api/sync/status` — last sync, pending corrections
- `POST /api/sync/shared` — push and pull for one period
- `POST` / `DELETE /api/sync/periods/{period}/ready` — mark ready, withdraw
- `POST` / `DELETE /api/sync/periods/{period}/paid` — mark paid, reopen (a month closed together
  reopens with the rest of its range)
- `GET /api/sync/close-together/preview?start=&end=` — what closing a range would settle
- `POST /api/sync/close-together` — close a range with one payment
- `POST /api/sync/corrections/{id}/acknowledge` — dismiss a correction
- `PUT /api/sync/peer-rows/{txn_id}/dispute` — raise or clear a dispute
- `PUT /api/transactions/{id}` — the inline repairs (who, split)

See also: [Splits & shared expenses](../concepts/splits.md), [Google Sheets setup](../getting-started/google-sheets.md).
