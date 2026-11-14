"""Loads the supplied reference data. Runs at startup, safe to run again.

INSERT OR IGNORE prevents duplicates reference records by checking if pkey exists
"""
import csv
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Manifest:
    dataset_id: str
    as_of: str                       # final valuation date, e.g. "2026-03-27"
    valuation_dates: frozenset[str]  # the only dates a trade may fall on


def load_manifest(data_dir: Path) -> Manifest:
    raw = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    return Manifest(
        dataset_id=raw["dataset_id"],
        as_of=raw["as_of"],
        valuation_dates=frozenset(raw["valuation_dates"]),
    )


# file name -> (table, columns in CSV header order)
REFERENCE_FILES = {
    "portfolios.csv": ("portfolios", ["portfolio_id", "name", "base_currency"]),
    "instruments.csv": ("instruments", ["instrument_id", "ticker", "name", "currency", "sector"]),
    "prices.csv": ("prices", ["instrument_id", "date", "close_price"]),
    "fx_rates.csv": ("fx_rates", ["date", "currency", "gbp_per_unit"]),
}


def load_reference(conn: sqlite3.Connection, data_dir: Path) -> None:
    for file_name, (table, columns) in REFERENCE_FILES.items():
        path = data_dir / "reference" / file_name
        with path.open(newline="", encoding="utf-8") as handle:
            rows = [tuple(row[c] for c in columns) for row in csv.DictReader(handle)]
        placeholders = ", ".join("?" for _ in columns)
        with conn:  # one transaction per file
            conn.executemany(
                f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                rows,
            )
            