"""Trade upload: validate everything first, then write all or nothing.

Three steps:
  1. validate_row   - each row on its own (format, known IDs, ranges)
  2. find_conflicts - rows against each other and against stored trades
  3. insert         - only if steps 1 and 2 found no errors, in one transaction
"""
import csv
import io
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

HEADER = ["trade_id", "portfolio_id", "instrument_id", "timestamp", "side", "quantity", "price"]
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$") #matches the ask in data contract
INTEGER_RE = re.compile(r"^\d+$") # enforcing digit only checks
PRICE_RE = re.compile(r"^\d+(\.\d+)?$")  # plain decimal text: no sign, no exponent, no NaN/inf


@dataclass(frozen=True)
class Trade:
    """A parsed trade. Two Trades are equal when every parsed value is
    equal, so Decimal("10.0") and Decimal("10.0000") count as the same."""
    trade_id: str
    portfolio_id: str
    instrument_id: str
    timestamp: str
    side: str
    quantity: int
    price: Decimal


@dataclass
class ImportResult:
    outcome: str = "imported"          # "imported" or "rejected"
    total_rows: int = 0
    inserted_rows: int = 0
    skipped_rows: int = 0
    invalid_rows: int = 0
    aborted_rows: int = 0
    file_error: str | None = None      # e.g. wrong header: no row counts apply
    errors: list[dict] = field(default_factory=list)  # {row, trade_id, reasons}


def validate_row(raw: dict[str, str], portfolios: set[str], instruments: set[str],
                 valid_dates: frozenset[str]) -> tuple[Trade | None, list[str]]:
    """Check one row. Returns (Trade, []) if clean, else (None, reasons).
    Collects every reason rather than stopping at the first."""
    reasons: list[str] = []

    for name in HEADER:
        if not raw.get(name):
            reasons.append(f"{name} is missing")
    if reasons:
        return None, reasons

    if raw["portfolio_id"] not in portfolios:
        reasons.append(f"unknown portfolio_id '{raw['portfolio_id']}'")
    if raw["instrument_id"] not in instruments:
        reasons.append(f"unknown instrument_id '{raw['instrument_id']}'")

    timestamp = raw["timestamp"]
    if not TIMESTAMP_RE.match(timestamp):
        reasons.append(f"timestamp must be exactly YYYY-MM-DDTHH:MM:SSZ, got '{timestamp}'")
    else:
        try:
            datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")  # rejects 2026-02-30 etc.
        except ValueError:
            reasons.append(f"timestamp is not a real date and time, got '{timestamp}'")
        else:
            if timestamp[:10] not in valid_dates:
                reasons.append(f"trade date {timestamp[:10]} is not a valuation date")

    if raw["side"] not in ("BUY", "SELL"):
        reasons.append(f"side must be BUY or SELL, got '{raw['side']}'")

    if not INTEGER_RE.match(raw["quantity"]) or int(raw["quantity"]) <= 0:
        reasons.append(f"quantity must be a positive whole number, got '{raw['quantity']}'")

    price_text = raw["price"]
    if not PRICE_RE.match(price_text) or Decimal(price_text) <= 0:
        reasons.append(f"price must be a positive decimal number, got '{price_text}'")
    elif "." in price_text and len(price_text.split(".")[1]) > 4:
        reasons.append(f"price has more than 4 decimal places, got '{price_text}'")

    if reasons:
        return None, reasons
    return Trade(raw["trade_id"], raw["portfolio_id"], raw["instrument_id"], timestamp,
                 raw["side"], int(raw["quantity"]), Decimal(price_text)), []


def _stored_trades(conn: sqlite3.Connection, trade_ids: list[str]) -> dict[str, Trade]:
    """Fetch already-stored trades for these IDs (in chunks: SQLite caps
    the number of ? placeholders per statement)."""
    found: dict[str, Trade] = {}
    for start in range(0, len(trade_ids), 500):
        chunk = trade_ids[start:start + 500]
        marks = ", ".join("?" for _ in chunk)
        for row in conn.execute(f"SELECT * FROM trades WHERE trade_id IN ({marks})", chunk):
            found[row["trade_id"]] = Trade(row["trade_id"], row["portfolio_id"], row["instrument_id"],
                                           row["timestamp"], row["side"], row["quantity"],
                                           Decimal(row["price"]))
    return found


def import_trades(conn: sqlite3.Connection, file_text: str,
                  valid_dates: frozenset[str]) -> ImportResult:
    result = ImportResult()
    rows = list(csv.reader(io.StringIO(file_text)))  # real CSV parsing: handles quoted commas

    if not rows or rows[0] != HEADER:
        result.outcome = "rejected"
        result.file_error = "header must be exactly: " + ",".join(HEADER)
        return result

    data_rows = rows[1:]
    result.total_rows = len(data_rows)
    portfolios = {r[0] for r in conn.execute("SELECT portfolio_id FROM portfolios")}
    instruments = {r[0] for r in conn.execute("SELECT instrument_id FROM instruments")}

    # Step 1: each row on its own. Row numbers count the header as row 1.
    parsed: dict[int, Trade] = {}
    errors: dict[int, dict] = {}

    def add_error(row_number: int, trade_id: str, reason: str) -> None:
        entry = errors.setdefault(row_number, {"row": row_number, "trade_id": trade_id, "reasons": []})
        entry["reasons"].append(reason)

    for row_number, cells in enumerate(data_rows, start=2):
        if len(cells) != len(HEADER):
            add_error(row_number, cells[0] if cells else "", f"expected {len(HEADER)} fields, found {len(cells)}")
            continue
        raw = dict(zip(HEADER, cells))
        trade, reasons = validate_row(raw, portfolios, instruments, valid_dates)
        if trade is None:
            for reason in reasons:
                add_error(row_number, raw["trade_id"], reason)
        else:
            parsed[row_number] = trade

    # Step 2: duplicates and conflicts, by trade_id.
    by_id: dict[str, list[int]] = {}
    for row_number, trade in parsed.items():
        by_id.setdefault(trade.trade_id, []).append(row_number)
    stored = _stored_trades(conn, list(by_id))

    to_insert: list[Trade] = []
    for trade_id, row_numbers in by_id.items():
        variants = {parsed[n] for n in row_numbers}
        if len(variants) > 1:
            for n in row_numbers:
                add_error(n, trade_id, "same trade_id appears in this file with different values")
        elif trade_id in stored:
            if stored[trade_id] != parsed[row_numbers[0]]:
                for n in row_numbers:
                    add_error(n, trade_id, "trade_id already stored with different values")
            # else: exact duplicate of a stored trade -> skipped
        else:
            to_insert.append(parsed[row_numbers[0]])  # insert once, repeats are skipped

    # Step 3: any error at all rejects the whole file; nothing is written.
    if errors:
        result.outcome = "rejected"
        result.errors = [errors[n] for n in sorted(errors)]
        result.invalid_rows = len(errors)
        result.aborted_rows = result.total_rows - result.invalid_rows
        return result

    with conn:  # one transaction: all rows commit together, or none do
        conn.executemany(
            "INSERT INTO trades (trade_id, portfolio_id, instrument_id, timestamp, side, quantity, price) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(t.trade_id, t.portfolio_id, t.instrument_id, t.timestamp, t.side, t.quantity, str(t.price))
             for t in to_insert],
        )
    result.inserted_rows = len(to_insert)
    result.skipped_rows = result.total_rows - result.inserted_rows
    return result
