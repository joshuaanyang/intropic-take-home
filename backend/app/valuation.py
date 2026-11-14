"""All the financial maths. Nothing here is stored: every figure is
recalculated from trades + reference data each time it is asked for.

For one instrument in one portfolio, as of date t (s = +1 BUY, -1 SELL):
    quantity     = sum(s * qty)
    net_cost_gbp = sum(s * qty * trade_price * fx_on_trade_day)
    market_value = quantity * latest_price(t) * latest_fx(t)
    pnl          = market_value - net_cost_gbp
"""
import sqlite3
from bisect import bisect_right
from decimal import ROUND_HALF_UP, Decimal

Series = list[tuple[str, Decimal]]  # [(date, value), ...] sorted by date


def money(value: Decimal) -> str:
    """Round to pennies for display only. Half-up: 0.125 -> 0.13."""
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def latest_on_or_before(series: Series, date: str) -> tuple[str, Decimal] | None:
    """Most recent (date, value) dated on or before `date`. Never looks
    forward. None if the series has nothing that early."""
    index = bisect_right(series, date, key=lambda item: item[0])
    return series[index - 1] if index else None


def _load_series(conn: sqlite3.Connection, sql: str, key: str) -> Series:
    return [(row["date"], Decimal(row["value"])) for row in conn.execute(sql, (key,))]


def price_series(conn: sqlite3.Connection, instrument_id: str) -> Series:
    return _load_series(conn, "SELECT date, close_price AS value FROM prices "
                              "WHERE instrument_id = ? ORDER BY date", instrument_id)


def fx_series(conn: sqlite3.Connection, currency: str) -> Series:
    return _load_series(conn, "SELECT date, gbp_per_unit AS value FROM fx_rates "
                              "WHERE currency = ? ORDER BY date", currency)


def build_position(instrument: dict, trades: list[dict], prices: Series, fx: Series, as_of: str) -> dict:
    """Value one instrument's trades. `trades` must already be limited to
    one portfolio, one instrument, and dates on or before as_of."""
    quantity = 0
    net_cost = Decimal(0)
    lines = []
    problem = None

    for trade in sorted(trades, key=lambda t: (t["timestamp"], t["trade_id"])):
        sign = 1 if trade["side"] == "BUY" else -1
        trade_date = trade["timestamp"][:10]
        rate = latest_on_or_before(fx, trade_date)  # FX on the trade's own day
        if rate is None:
            problem = f"no {instrument['currency']} FX rate on or before {trade_date}"
            break
        fx_date, fx_value = rate
        cost = sign * trade["quantity"] * Decimal(trade["price"]) * fx_value
        quantity += sign * trade["quantity"]
        net_cost += cost
        lines.append({
            "trade_id": trade["trade_id"], "timestamp": trade["timestamp"], "side": trade["side"],
            "quantity": trade["quantity"], "price": trade["price"],
            "fx_rate": str(fx_value), "fx_date": fx_date,
            "signed_cost_gbp": money(cost), "running_quantity": quantity,
        })

    position = {
        "instrument_id": instrument["instrument_id"], "ticker": instrument["ticker"],
        "name": instrument["name"], "currency": instrument["currency"],
        "quantity": quantity, "closed": quantity == 0, "trades": lines,
        "price": None, "price_date": None, "price_carried_forward": False,
        "fx_rate": None, "fx_date": None,
        "net_cost_gbp": None, "market_value_gbp": None, "pnl_gbp": None,
        "error": problem, "_market_value": None, "_pnl": None,
    }
    if problem:
        return position

    price = latest_on_or_before(prices, as_of)   # independently the latest price...
    rate = latest_on_or_before(fx, as_of)        # ...and the latest FX rate
    if price:
        position["price_date"], position["price"] = price[0], str(price[1])
        position["price_carried_forward"] = price[0] != as_of
    if rate:
        position["fx_date"], position["fx_rate"] = rate[0], str(rate[1])

    if quantity == 0:
        market_value = Decimal(0)                # closed: worth nothing, P&L remains
    elif price is None or rate is None:
        position["error"] = f"no price or FX rate on or before {as_of}"
        return position
    else:
        market_value = quantity * price[1] * rate[1]

    pnl = market_value - net_cost
    position.update(net_cost_gbp=money(net_cost), market_value_gbp=money(market_value),
                    pnl_gbp=money(pnl), _market_value=market_value, _pnl=pnl)
    return position


def portfolio_summary(conn: sqlite3.Connection, portfolio_id: str, as_of: str) -> dict:
    """Every position in a portfolio plus totals. Totals are summed from
    unrounded values and rounded once, so they can differ from the sum
    of the rounded rows by a penny or two."""
    trades = [dict(row) for row in conn.execute(
        "SELECT * FROM trades WHERE portfolio_id = ? AND substr(timestamp, 1, 10) <= ?",
        (portfolio_id, as_of))]
    by_instrument: dict[str, list[dict]] = {}
    for trade in trades:
        by_instrument.setdefault(trade["instrument_id"], []).append(trade)

    fx_cache: dict[str, Series] = {}
    positions = []
    for instrument_id in sorted(by_instrument):
        instrument = dict(conn.execute("SELECT * FROM instruments WHERE instrument_id = ?",
                                       (instrument_id,)).fetchone())
        currency = instrument["currency"]
        if currency not in fx_cache:
            fx_cache[currency] = fx_series(conn, currency)
        positions.append(build_position(instrument, by_instrument[instrument_id],
                                        price_series(conn, instrument_id), fx_cache[currency], as_of))

    failed = [p["instrument_id"] for p in positions if p["error"]]
    summary = {"portfolio_id": portfolio_id, "as_of": as_of, "trade_count": len(trades),
               "market_value_gbp": None, "pnl_gbp": None, "unavailable": failed}
    if not failed:  # a total with a missing piece would be a fabricated number
        summary["market_value_gbp"] = money(sum((p["_market_value"] for p in positions), Decimal(0)))
        summary["pnl_gbp"] = money(sum((p["_pnl"] for p in positions), Decimal(0)))
    for position in positions:
        del position["_market_value"], position["_pnl"]
    summary["positions"] = positions
    return summary