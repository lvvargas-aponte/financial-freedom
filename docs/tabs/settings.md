# Settings

> Source: `frontend/src/components/settings/SettingsPage.js`, `panes/*`, `backend/routers/profile.py`, `backend/routers/categories.py`, `backend/routers/category_rules.py`

Reached at `/settings`, or deep-linked to a pane at `/settings/{pane}`. Two panes: **Financial profile**
and **Categories & rules**. The profile is a form — edits collect in a draft and **Save** commits them
together, and leaving with unsaved changes warns first. Categories and rules are not part of that
draft: each edit is its own server call and takes effect as you make it.

## Financial profile

What Fin knows about your situation that your transactions cannot tell it. Everything here feeds the
advisor's grounding context and several ratios on [Home](home.md).

| Card | Fields |
|---|---|
| **Risk & horizon** | Risk tolerance (conservative / balanced / aggressive), horizon in years, dependents, monthly take-home |
| **Debt & reserves** | Debt-payoff strategy (avalanche / snowball / minimums only), emergency-fund target (3/6/9/12 months) |
| **Retirement** *(optional)* | Birth year, target retirement age, annual spend in retirement, expected return % |
| **Tax** *(optional)* | Marginal tax rate %, and a **Show after-tax net worth** toggle that adds a second line to Home's hero |
| **Context** *(optional)* | Free-text notes for the advisor |

The emergency-fund target is what the **Runway** reading on Home is measured against; monthly
take-home is the denominator of the debt-to-income ratio on [Debt](debt.md).

Backend: `GET` / `PUT /api/profile`.

## Categories & rules

One list, not two. A rule exists to pick a category, so it lives **inside** the category it picks —
there is nothing to cross-reference. Each row shows the category's colour, its roles, how many rules
feed it, its transaction count and this month's spend; the filter box matches rule patterns as well
as names, so searching a merchant finds the category it lands in. **Show archived** brings back the
ones you have retired.

Expanding a row gives everything about that category in one place:

| Control | What it does |
|---|---|
| **Name** | Renaming rewrites every transaction, budget and rule that uses it. Renaming onto a name that already exists merges into it. |
| **Grouped under** | Puts this category inside a parent, one level deep — spending from the children rolls up. A category that already holds others cannot itself be nested. |
| **Merge into** | Folds this category into another and deletes it. The survivor gains both role sets. |
| **Archive** / **Delete** | Archive retires a category without touching history; Delete clears it from every transaction using it. A budget under that name survives either way. |
| **Rules that pick it** | Every rule feeding this category, **in evaluation order** — first match wins. Each can be switched off or deleted, and shows when it last matched. |
| **Add text rule** | "When the description contains *this*, use this category." |
| **How it behaves** | The role checkboxes — see below. |

### Rule order

Two kinds of rule, and the order is the answer when both could match:

- **Merchant rules** run first and carry no number, because their position is not a choice. They are
  what the *"always categorize CHIPOTLE as Dining"* prompt writes when you categorize a transaction —
  see [Transactions → Current](transactions-current.md#remember-a-merchant).
- **Text rules** run after, numbered in the order they are evaluated. Matching is a case-insensitive
  **substring** test — deliberately not regex, so a malformed pattern fails to match rather than
  raising mid-categorisation.

Rules are consulted by `categorizer.suggest_category` **before** it reaches for Ollama, so a rule you
wrote always beats the model's guess and still answers when Ollama is down. Adding a rule here does
not retroactively recategorise history — the rule prompt on Transactions offers that sweep at the
moment you write the rule, and [Transactions → History](transactions-history.md) is where you clean
up after the fact.

### Roles

Roles are what a category *means* to the rest of the app, and each one changes something concrete:

| Role | What it changes |
|---|---|
| **Not spending** | Moves money between your own accounts — kept out of spending totals |
| **Varies monthly** | Still a recurring bill when the amount swings |
| **Bill** | Shows under Bills |
| **Subscription** | Shows under Commitments, and counts toward overlap warnings |
| **Not a commitment** | A consequence of a balance, like interest or fees |

Unlike the profile pane, nothing here waits for **Save** — every edit is its own server call and
lands immediately.

Backend: `GET` / `POST /api/categories`, `PATCH /api/categories/{id}`, `/rename`, `/merge`,
`/parent`, `DELETE /api/categories/id/{id}`, `GET /api/categories/roles`, and
`GET` / `POST /api/category-rules` with `PATCH` / `DELETE /api/category-rules/{id}`.

## What is not here

- **Dark mode** and **Help** live in the sidebar footer, not in Settings.
- **Bank and brokerage connections** live on [Accounts](accounts.md).
- **Person names** for shared splits come from environment variables — see
  [Environment variables](../getting-started/env-vars.md).
