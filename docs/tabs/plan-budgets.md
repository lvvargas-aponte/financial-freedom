# Plan → Budgets

> Source: `frontend/src/components/finances/BudgetsSection.js`, `BudgetPresetModal.js`, `backend/routers/budgets.py`

Reached at `/plan/budgets`. Set a monthly spending limit per category. Home's **Budgets** card and its **Needs you** feed both read from these.

## What you see

A table of categories with:

- Monthly limit ($)
- Current month's spend
- Progress bar
- Edit / delete actions

## Start from a preset

**Use a preset** builds a whole month's budgets at once from a percentage rule, in two steps.

1. **Pick a rule and confirm your income** — **50/30/20** (classic), **70/20/10** (tight budget),
   **60/20/20** (balanced), or **80/10/10** (high cost-of-living). The monthly take-home figure is
   pre-filled from what the app already measured (`GET /api/health/ratios`) rather than asked for a
   third time; you can type over it.
2. **Sort your categories** into **Needs** / **Wants** / **Savings** / **Skip**. Each category is
   pre-sorted by keywords in its name, and each bucket's share of income is split evenly across the
   categories in it — move one and the rest re-divide. Per-category amounts can be typed over.

Before applying, the modal says how many existing budgets will be overwritten. **Apply budgets**
upserts each one with a note recording the rule and bucket it came from (e.g. `50/30/20 · Needs`).

## Common actions

- **Add a budget** — **+ Add Budget**, pick a category, enter a monthly limit.
- **Start from a preset** — **Use a preset**, see above.
- **Edit** — click the limit; save in place.
- **Delete** — removes the budget; spending in that category no longer triggers alerts.

## Under the hood

- `GET /api/budgets` — list with current-month spend
- `PUT /api/budgets/{category}` — upsert a limit
- `DELETE /api/budgets/{category}` — remove

Budget over-runs surface in the [Needs you feed](home.md#needs-you) and are visible to Fin through its `get_budget_status` tool.

See also: [Budgets & goals concept](../concepts/budgets-and-goals.md).
