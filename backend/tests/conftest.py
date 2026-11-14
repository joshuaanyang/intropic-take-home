"""A tiny made-up dataset so tests do not depend on the supplied files."""
import json

import pytest

from app import db, reference

DATES = ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]


@pytest.fixture
def data_dir(tmp_path):
    ref = tmp_path / "reference"
    ref.mkdir()
    (ref / "portfolios.csv").write_text("portfolio_id,name,base_currency\nP001,Test Fund,GBP\n")
    (ref / "instruments.csv").write_text(
        "instrument_id,ticker,name,currency,sector\n"
        "I001,ZZGBP,\"Sterling, Co\",GBP,Financials\n"
        "I002,ZZUSD,Dollar Co,USD,Technology\n")
    # I001 has no price on the last day -> carried forward from 01-07
    (ref / "prices.csv").write_text(
        "instrument_id,date,close_price\n"
        "I001,2026-01-05,10\nI001,2026-01-06,15\nI001,2026-01-07,16\n"
        "I002,2026-01-05,10\nI002,2026-01-08,12\n")
    (ref / "fx_rates.csv").write_text(
        "date,currency,gbp_per_unit\n"
        "2026-01-05,GBP,1.000000\n2026-01-05,USD,0.80\n2026-01-08,USD,0.75\n")
    (tmp_path / "manifest.json").write_text(json.dumps(
        {"dataset_id": "ds-test", "as_of": DATES[-1], "valuation_dates": DATES}))
    return tmp_path


@pytest.fixture
def conn(data_dir, tmp_path):
    connection = db.connect(str(tmp_path / "test.db"))
    db.create_tables(connection)
    reference.load_reference(connection, data_dir)
    yield connection
    connection.close()


@pytest.fixture
def manifest(data_dir):
    return reference.load_manifest(data_dir)
