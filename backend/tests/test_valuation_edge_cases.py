"""Edge cases from contract section 4 that the worked examples do not reach."""
from app.importer import import_trades
from app.valuation import portfolio_summary

HEADER = "trade_id,portfolio_id,instrument_id,timestamp,side,quantity,price\n"


def load(conn, manifest, body):
    assert import_trades(conn, HEADER + body, manifest.valuation_dates).outcome == "imported"


def test_missing_price_gives_unavailable_not_a_made_up_number(conn, manifest):
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,10,10\n")
    conn.execute("DELETE FROM prices WHERE instrument_id = 'I001'")  # no price at all
    summary = portfolio_summary(conn, "P001", manifest.as_of)
    position = summary["positions"][0]
    assert position["error"] and position["market_value_gbp"] is None
    assert summary["unavailable"] == ["I001"]
    assert summary["market_value_gbp"] is None and summary["pnl_gbp"] is None


def test_missing_trade_day_fx_gives_unavailable(conn, manifest):
    load(conn, manifest, "T1,P001,I002,2026-01-05T09:00:00Z,BUY,10,10\n")
    conn.execute("DELETE FROM fx_rates WHERE currency = 'USD'")
    summary = portfolio_summary(conn, "P001", manifest.as_of)
    assert "USD FX rate" in summary["positions"][0]["error"]
    assert summary["pnl_gbp"] is None


def test_trades_after_the_valuation_date_are_excluded(conn, manifest):
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n"
                         "T2,P001,I001,2026-01-07T09:00:00Z,BUY,50,12\n")
    summary = portfolio_summary(conn, "P001", "2026-01-06")  # value as of an earlier date
    position = summary["positions"][0]
    assert summary["trade_count"] == 1 and position["quantity"] == 100
    assert position["price_date"] == "2026-01-06"  # and the price of that date, not a later one


def test_totals_are_summed_before_rounding(conn, manifest):
    # P&L per position: 15.996 and 8.996. Each rounds up (16.00 + 9.00 = 25.00),
    # but the unrounded sum is 24.992, so the correct total is 24.99.
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,1,0.004\n"
                         "T2,P001,I002,2026-01-05T09:00:00Z,BUY,1,0.005\n")
    summary = portfolio_summary(conn, "P001", manifest.as_of)
    assert [p["pnl_gbp"] for p in summary["positions"]] == ["16.00", "9.00"]
    assert summary["pnl_gbp"] == "24.99"
