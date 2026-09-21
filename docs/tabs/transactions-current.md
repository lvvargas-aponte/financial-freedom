# Transactions → Current

> Source: `frontend/src/components/transactions/TransactionsPage.js`, `frontend/src/components/transactions/*`, `frontend/src/hooks/useSyncFlow.js`, `backend/routers/transactions.py`

Reached at `/transactions`. A review queue of every transaction (SimpleFIN-synced + CSV-uploaded) where you mark splits, add notes, categorize, and send shared expenses to Google Sheets.

The three Transactions views split by purpose: **Current** is the review queue, [**Shared**](transactions-shared.md) is where the two-person settle-up happens, and [**History**](transactions-history.md) is the full record for cleaning up categories after the fact.

## What you see

| Element | What it does |
|---|---|
| **Sync panel** (top banner) | Shows last sync time and account status. Buttons: **Sync Banks**, **Accounts**. See [Sync panel section below](#sync-panel). |
| **Control bar** | Stats pills (total / shared count / shared amount / unreviewed). Buttons: **↑ Upload CSV**, **⎘ Find duplicates**, **↗ Send to Sheet (n)**. |
| **Bulk bar** (only when rows selected) | Selected count and the shared amount in the selection, then **Mark personal**, **Split 50/50**, **✓ Mark reviewed**, **↺ Mark unreviewed**, **✨ Suggest**, and **✕** to clear the selection. |
| **Filter bar** | Bank dropdown, month dropdown, split-type dropdown, search box. Shows visible/total count. |
| **Transaction table** | One row per transaction. Inline split toggle, type flip, note + adjust expanders. Clicking a row expands the [transaction detail editor](../modals/edit-transaction.md) beneath it. |
| **Supporting rail** (right side) | Review progress, shared-with-person total, category breakdown, and — when a row is expanded — "Apply to similar". See [Supporting rail](#supporting-rail). |

## Supporting rail

A column of cards to the right of the table, on both **Current** and **History**. Every figure is computed from the *currently filtered* rows, not the whole account.

| Card | What it shows |
|---|---|
| **Review progress** | How many visible rows are reviewed, with a progress bar and a jump-to-next-unreviewed button. |
| **Apply to similar** | Only while a row is expanded and other rows share its merchant. Applies the open row's category / shared flag to all matches at once. |
| **Shared with \<person\>** | Running total of shared amounts in view, with a **Send to Sheet** shortcut. |
| **Where it went** | Top spending categories in view, ranked with bars. |

The rail is pinned — it stays in place as you scroll the table. Below ~1600px of window width there isn't room beside the table, so the cards stack underneath it and scroll with the page instead.

## Common workflows

### Mark a single transaction as a 50/50 shared split

1. Click the **½** pill on the row. The split is saved instantly and the row marks as reviewed.

### Add a custom split

1. Click **🧮** on the row → an inline adjust panel opens below it.
2. Enter how much each person owes, or click **50/50** for a quick equal split.
3. Save.

### Edit several fields at once

1. Click the row → the [transaction detail editor](../modals/edit-transaction.md) expands beneath it.
2. Change category, split, type, reviewed state, notes.
3. **Save**. **Collapse** closes the editor.

### Add a note

1. Click **🗒️** → an inline note editor opens.
2. Type, save. The icon becomes **📝** to show a note exists.

### Bulk-mark many rows

1. Tick the checkboxes (or the header checkbox to select all visible).
2. Use **Mark personal** or **50/50 split** in the bulk bar.

### Get AI-suggested categories

1. Select rows.
2. Click **Suggest** → opens the [Suggest Categories preview modal](../modals/suggest-preview.md).
3. Review per-row suggestions and apply.

After a bank sync or a CSV upload this happens on its own: once the new rows land, Current asks for
suggestions for the ones that arrived without a category and opens the same preview. A banner shows
while it works. Nothing is applied until you confirm, and applying a category never marks a row
reviewed. If you are on another page when the sync finishes, the preview waits until you open
Current.

### Remember a merchant

Right after you set a row's category, a prompt appears beneath it: **Always categorize ⟨merchant⟩ as
⟨category⟩**, checked by default — categorizing the same merchant over and over is the tedium it
exists to end. When other transactions from that merchant are already imported it offers a second,
*unchecked* box to sweep them too, since that rewrites rows you can already see.

Rows a higher source already owns — ones you categorized by hand, or that a rule claimed — are never
touched, and the prompt says how many it is leaving alone. **Remember** writes a merchant rule (it
shows up under its category in [Settings](settings.md#categories-rules)); **Not now** dismisses it
and stops asking about that merchant for the rest of the session. The prompt is skipped entirely when
the merchant already has a rule.

Backend: `GET /api/category-rules/for-merchant`, `POST /api/category-rules/preview`,
`POST /api/category-rules` with `apply_to_existing`.

### Send shared expenses to Google Sheets

1. Click **↗ Send to Sheet (n)** in the control bar — *n* is the number of shared rows in view.
2. Confirm. If a single month is selected in the filter bar, only that period syncs; otherwise every
   shared row does.
3. Your rows are pushed to the sheet and the peer's are pulled back in the same call. It is a
   **two-way sync keyed by `Txn ID`**, not an append — running it twice does not duplicate rows.
   Your local records are kept either way.

A refused sync (a period already marked paid, say) reports the refusal; a cycle that fails reports
the failure rather than a success toast counting rows that were never written. See
[Transactions → Shared](transactions-shared.md) for the settle-up side of this.

### Upload a CSV

1. Click **📂 Upload CSV** and pick a Discover or Barclays CSV.
2. The [Upload CSV modal](../modals/upload-csv.md) opens for account/balance metadata.
3. Submit → rows appear in the table.

## Sync panel

Shows account-connection health and last sync time. The buttons open:

- **Sync Banks** → [Sync Bank modal](../modals/sync-bank.md)
- **Accounts** → [Linked Accounts modal](../modals/accounts-modal.md)

See also: [Bank sync concept](../concepts/bank-sync.md).

## Under the hood

- Transactions endpoint: `GET /api/transactions/all`
- Single edit: `PUT /api/transactions/{id}`
- Bulk edit: `PUT /api/transactions/bulk`
- Bulk suggest: `POST /api/transactions/suggest-categories/bulk`
- Send to Sheet: `POST /api/sync/shared` (two-way, month-scoped)
- Remember a merchant: `GET /api/category-rules/for-merchant`, `POST /api/category-rules/preview`, `POST /api/category-rules`
