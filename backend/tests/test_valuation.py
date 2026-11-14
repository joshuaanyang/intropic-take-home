from decimal import Decimal

from app.importer import import_trades
from app.valuation import latest_on_or_before, money, portfolio_summary

HEADER = "trade_id,portfolio_id,instrument_id,timestamp,side,quantity,price\n"


def load(conn, manifest, body):
    assert import_trades(conn, HEADER + body, manifest.valuation_dates).outcome == "imported"


def position(conn, manifest, instrument_id):
    summary = portfolio_summary(conn, "P001", manifest.as_of)
    return next(p for p in summary["positions"] if p["instrument_id"] == instrument_id), summary


def test_contract_example_gbp_trades(conn, manifest):
    # Buy 100 @ 10, sell 40 @ 15, buy 20 @ 12, ending price 16
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n"
                         "T2,P001,I001,2026-01-06T09:00:00Z,SELL,40,15\n"
                         "T3,P001,I001,2026-01-07T09:00:00Z,BUY,20,12\n")
    p, _ = position(conn, manifest, "I001")
    assert p["quantity"] == 80
    assert (p["net_cost_gbp"], p["market_value_gbp"], p["pnl_gbp"]) == ("640.00", "1280.00", "640.00")


def test_contract_example_fx_uses_trade_day_rate(conn, manifest):
    # Buy 100 @ USD 10 when USD = 0.80; later USD 12 at 0.75
    load(conn, manifest, "T1,P001,I002,2026-01-05T09:00:00Z,BUY,100,10\n")
    p, _ = position(conn, manifest, "I002")
    assert (p["net_cost_gbp"], p["market_value_gbp"], p["pnl_gbp"]) == ("800.00", "900.00", "100.00")
    assert (p["fx_rate"], p["fx_date"]) == ("0.75", "2026-01-08")
    assert p["trades"][0]["fx_rate"] == "0.80"


def test_contract_example_closed_position(conn, manifest):
    # Buy 10 @ 10, sell 10 @ 12
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,10,10\n"
                         "T2,P001,I001,2026-01-06T09:00:00Z,SELL,10,12\n")
    p, summary = position(conn, manifest, "I001")
    assert (p["quantity"], p["closed"]) == (0, True)
    assert (p["market_value_gbp"], p["pnl_gbp"]) == ("0.00", "20.00")
    assert summary["pnl_gbp"] == "20.00"  # closed positions still count in the total


def test_price_is_carried_forward_and_flagged(conn, manifest):
    load(conn, manifest, "T1,P001,I001,2026-01-05T09:00:00Z,BUY,1,10\n")
    p, _ = position(conn, manifest, "I001")
    assert (p["price"], p["price_date"], p["price_carried_forward"]) == ("16", "2026-01-07", True)


def test_trade_order_in_file_does_not_matter(conn, manifest):
    load(conn, manifest, "T2,P001,I001,2026-01-06T09:00:00Z,SELL,40,15\n"
                         "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n")
    p, _ = position(conn, manifest, "I001")
    assert [line["running_quantity"] for line in p["trades"]] == [100, 60]


def test_never_looks_forward():
    series = [("2026-01-05", Decimal("1")), ("2026-01-08", Decimal("2"))]
    assert latest_on_or_before(series, "2026-01-07") == ("2026-01-05", Decimal("1"))
    assert latest_on_or_before(series, "2026-01-04") is None


def test_rounding_is_half_up():
    assert money(Decimal("0.125")) == "0.13"
    assert money(Decimal("-0.125")) == "-0.13"
    assert money(Decimal("2.675")) == "2.68"
