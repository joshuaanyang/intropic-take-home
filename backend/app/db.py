"""Storage only: where the database lives and what the tables look like.

No business rules in this file. Dates and timestamps are ISO text
(YYYY-MM-DD...), which sorts correctly as plain text. Prices and FX
rates are stored as TEXT so no precision is lost; Python turns them
into Decimal when it calculates.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolios (
    portfolio_id  TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    base_currency TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS instruments (
    instrument_id TEXT PRIMARY KEY,
    ticker        TEXT NOT NULL,
    name          TEXT NOT NULL,
    currency      TEXT NOT NULL,
    sector        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS prices (
    instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
    date          TEXT NOT NULL,
    close_price   TEXT NOT NULL,
    PRIMARY KEY (instrument_id, date)
);
CREATE TABLE IF NOT EXISTS fx_rates (
    date         TEXT NOT NULL,
    currency     TEXT NOT NULL,
    gbp_per_unit TEXT NOT NULL,
    PRIMARY KEY (date, currency)
);
CREATE TABLE IF NOT EXISTS trades (
    trade_id      TEXT PRIMARY KEY,
    portfolio_id  TEXT NOT NULL REFERENCES portfolios(portfolio_id),
    instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
    timestamp     TEXT NOT NULL,
    side          TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    price         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_portfolio
    ON trades (portfolio_id, instrument_id);
"""


def connect(path: str) -> sqlite3.Connection:
    # Each request opens its own connection, so one connection is never
    # shared between two requests. FastAPI may still hand a request to a
    # different worker thread than the one that opened it, hence the flag.
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row          # rows like dicts: row["price"] easier than tules
    conn.execute("PRAGMA foreign_keys = ON")  # -ignores unknown portfolios x instruments not in REF
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
