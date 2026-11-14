"""Web routes. each one calls a function from
importer.py or valuation.py and returns the result as JSON."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from . import db, importer, reference, valuation

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DB_PATH = os.environ.get("DB_PATH", "portfolio.db")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup: make tables, load reference data."""
    conn = db.connect(DB_PATH)
    db.create_tables(conn)
    reference.load_reference(conn, DATA_DIR)
    conn.close()
    app.state.manifest = reference.load_manifest(DATA_DIR)
    yield


app = FastAPI(title="Portfolio Investigation Tool", lifespan=lifespan)


def get_conn():
    """A fresh connection per request, always closed afterwards."""
    conn = db.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/api/meta")
def meta():
    manifest = app.state.manifest
    return {"dataset_id": manifest.dataset_id, "as_of": manifest.as_of}


@app.post("/api/imports")
async def upload_trades(file: UploadFile, conn=Depends(get_conn)):
    try:
        text = (await file.read()).decode("utf-8-sig")  # utf-8, tolerating a BOM
    except UnicodeDecodeError:
        return JSONResponse(status_code=422, content={"outcome": "rejected",
                                                      "file_error": "file is not UTF-8 text"})
    result = importer.import_trades(conn, text, app.state.manifest.valuation_dates)
    status = 200 if result.outcome == "imported" else 422
    return JSONResponse(status_code=status, content=result.__dict__)


@app.get("/api/portfolios")
def list_portfolios(conn=Depends(get_conn)):
    return [dict(row) for row in conn.execute("SELECT * FROM portfolios ORDER BY portfolio_id")]


def _summary(conn, portfolio_id: str) -> dict:
    if not conn.execute("SELECT 1 FROM portfolios WHERE portfolio_id = ?", (portfolio_id,)).fetchone():
        raise HTTPException(status_code=404, detail=f"unknown portfolio '{portfolio_id}'")
    return valuation.portfolio_summary(conn, portfolio_id, app.state.manifest.as_of)


@app.get("/api/portfolios/{portfolio_id}")
def portfolio(portfolio_id: str, conn=Depends(get_conn)):
    summary = _summary(conn, portfolio_id)
    for position in summary["positions"]:
        del position["trades"]  # the summary screen does not need every trade
    return summary


@app.get("/api/portfolios/{portfolio_id}/positions/{instrument_id}")
def position(portfolio_id: str, instrument_id: str, conn=Depends(get_conn)):
    for item in _summary(conn, portfolio_id)["positions"]:
        if item["instrument_id"] == instrument_id:
            return item
    raise HTTPException(status_code=404, detail=f"no trades for '{instrument_id}' in '{portfolio_id}'")

