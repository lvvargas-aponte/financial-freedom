"""The settlement footer — one month on its own, or one of several closed together."""
from decimal import Decimal

from sheet_sync import contract, footer
from sheet_sync.gateway import InMemoryGateway

P1, P2 = "Valeria", "Christy"
HEADERS = contract.build_headers(P1, P2)
INDEX = contract.header_index_map(HEADERS, P1, P2)
TITLE = "July 2026"


def txn(txn_id, owes_1="", owes_2=""):
    row = [""] * len(HEADERS)
    row[INDEX["date"]] = "07/10/2026"
    row[INDEX["description"]] = "Groceries"
    row[INDEX["amount"]] = "100"
    row[INDEX["who"]] = P1 if owes_2 else P2
    row[INDEX["owes_1"]] = owes_1
    row[INDEX["owes_2"]] = owes_2
    row[INDEX["txn_id"]] = txn_id
    return row


def sheet():
    # Christy owes 60, Valeria owes 20: Christy pays Valeria 40.
    return InMemoryGateway({TITLE: [HEADERS[:], txn("a", owes_2="60"), txn("b", owes_1="20")]})


def write(gw, closing=None, method=None):
    return footer.write(
        gw, TITLE, gw.read_rows(TITLE), INDEX,
        person_1_name=P1, person_2_name=P2, method=method, closing=closing,
    )


def who_column(gw):
    return [r[INDEX["who"]] for r in gw.read_rows(TITLE)]


def cell(gw, row, key):
    raw = gw.read_rows(TITLE)[row - 1]
    return raw[INDEX[key]] if INDEX[key] < len(raw) else ""


MIDDLE = footer.Closing(label="June–August 2026", summary_title="August 2026")
SUMMARY = footer.Closing(
    label="June–August 2026",
    summary_title="August 2026",
    months=(
        ("June 2026", Decimal("-30")),
        ("July 2026", Decimal("40")),
        ("August 2026", Decimal("20")),
    ),
    total=Decimal("30"),
)


class TestOneMonth:
    def test_totals_then_the_payment_line(self):
        gw = sheet()
        written = write(gw)

        assert written.totals_row == 5
        assert cell(gw, 5, "owes_1") == "$20.00"
        assert cell(gw, 5, "owes_2") == "$60.00"
        assert cell(gw, 7, "who") == "Christy pays Valeria via Zelle"
        assert cell(gw, 7, "owes_1") == "$40.00"

    def test_rewriting_does_not_stack_a_second_footer(self):
        gw = sheet()
        write(gw)
        write(gw)

        assert len(gw.read_rows(TITLE)) == 7


class TestClosedTogether:
    def test_a_middle_month_points_at_the_summary_and_carries_no_amount(self):
        gw = sheet()
        write(gw, closing=MIDDLE)

        assert cell(gw, 5, "owes_2") == "$60.00"   # its own totals stay
        assert cell(gw, 7, "who") == "Closed together June–August 2026 · see August 2026"
        assert cell(gw, 7, "owes_1") == ""

    def test_the_summary_month_lists_each_month_and_pays_the_total(self):
        gw = sheet()
        write(gw, closing=SUMMARY, method="via Venmo")

        assert who_column(gw)[6:] == [
            "Closed together June–August 2026 (aggregated):",
            "June 2026: Valeria owes Christy $30.00",
            "July 2026: Christy owes Valeria $40.00",
            "August 2026: Christy owes Valeria $20.00",
            "Christy pays Valeria via Venmo",
        ]
        assert cell(gw, 11, "owes_1") == "$30.00"

    def test_a_summary_is_recognised_and_rewritten_in_place(self):
        gw = sheet()
        write(gw, closing=SUMMARY)
        write(gw, closing=SUMMARY)

        assert len(gw.read_rows(TITLE)) == 11

    def test_a_middle_month_note_is_recognised_on_a_rerun(self):
        gw = sheet()
        write(gw, closing=MIDDLE)
        write(gw, closing=MIDDLE)

        assert len(gw.read_rows(TITLE)) == 7

    def test_reopening_a_summary_leaves_no_breakdown_behind(self):
        gw = sheet()
        write(gw, closing=SUMMARY)
        write(gw)

        assert cell(gw, 7, "who") == "Christy pays Valeria via Zelle"
        assert cell(gw, 7, "owes_1") == "$40.00"
        assert [cell(gw, r, "who") for r in range(8, 12)] == ["", "", "", ""]
        assert cell(gw, 11, "owes_1") == ""

    def test_a_single_footer_growing_into_a_summary_drops_the_old_amount(self):
        gw = sheet()
        write(gw)
        write(gw, closing=SUMMARY)

        # Row 7 held "$40.00" as the old payment line; it is now a heading.
        assert cell(gw, 7, "owes_1") == ""
        assert cell(gw, 11, "owes_1") == "$30.00"


class TestMonthLine:
    def test_an_even_month_says_so(self):
        assert footer.month_line("June 2026", Decimal("0"), P1, P2) == "June 2026: even"
