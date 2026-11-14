# Portfolio Investigation Tool

Upload trade files, see each portfolio's holdings market value and cumulative
P&L in GBP, and drill from a total down to the trades and valuation inputs
behind it.

Dataset identifier (from `data/manifest.json`): **`ds-c939fb471e09c6d8`**

## 1. Prerequisites, startup and access

**Prerequisite:** Docker Desktop (or Docker Engine with the Compose plugin).
Nothing else. No Python or Node is needed on the host.

**Start (one command, from the repository root):**

```
docker compose up --build
```

**Open:** http://localhost:8000

- Reference data (portfolios, instruments, prices, FX) loads automatically at
  startup. Restarting does not duplicate it.
- Trade files are **not** loaded automatically. Upload them on the Upload tab
  from `data/uploads/`, in this order: `trades_initial.csv`,
  `trades_repeat.csv`, `trades_incremental.csv`, `trades_invalid.csv`,
  `trades_corrected.csv`.
- Imported trades are kept on a Docker volume, so they survive
  `docker compose down` and `docker compose up`.
- `RECEIVED_PACK_README.md` is the cover note supplied with the exercise,
  renamed so that this file could be `README.md`.
- To wipe the database and start clean: `docker compose down -v`.

## 2. Running the tests

```
docker compose run --rm app pytest
```

Or without Docker (Python 3.11+):

```
cd backend
pip install -r requirements.txt
pytest
```

For development without Docker, run `uvicorn app.main:app --reload` in
`backend/` and `npm install` then `npm run dev` in `frontend/`; the page is
then at http://localhost:5173 and forwards `/api` calls to port 8000.

The tests build a small made-up dataset in `backend/tests/conftest.py`, so
they do not depend on the supplied files. They cover:

- the contract's three worked examples (640, 100 and 20 GBP);
- trade-day FX for cost and valuation-date FX for value;
- carry-forward pricing, never looking forward, half-up rounding;
- totals summed before rounding, and trades after the valuation date excluded;
- an "unavailable" result when a price or FX rate is missing;
- every import rule: repeat, overlap, in-file duplicates, conflicts within a
  file and with stored trades, each kind of invalid row, atomic rejection.

**Result on the supplied files** (uploaded in the contract's order, in Docker):

| File | Outcome |
|---|---|
| `trades_initial.csv` | imported: 600 inserted |
| `trades_repeat.csv` | imported: 0 inserted, 600 skipped |
| `trades_incremental.csv` | imported: 60 inserted |
| `trades_invalid.csv` | rejected: 8 invalid, 2 aborted, store unchanged |
| `trades_corrected.csv` | imported: 10 inserted (670 stored in total) |

## 3. Main design choices and assumptions

**Shape.** A FastAPI JSON API, a small React front end, and a SQLite file.
In Docker the React app is built once and served by the same FastAPI process,
so there is one container, one port and one command.

| Choice | Why |
|---|---|
| React + Docker Compose | The brief leaves frameworks open, but `DATA_CONTRACT.md` says uploads "must enter through the React upload flow" and refers to Compose. This satisfies both. |
| SQLite | Trades must survive a restart and the reviewer must run it with no setup. One user and a few hundred rows do not need a database server. |
| `trade_id` as primary key | The contract calls it globally unique. The database itself then refuses a duplicate, whatever the code does. |
| Prices and FX stored as text, maths in Python `Decimal` | SQLite has no exact decimal type. The contract requires exact arithmetic. |
| Nothing computed is stored | The brief says not to substitute precomputed answers. Every figure is recalculated from stored trades and reference data on each request. |
| Validate the whole file, then write in one transaction | "Atomic per file": a rejected file leaves stored trades untouched, and the user sees every problem at once. |
| All valuation logic in `backend/app/valuation.py` | One short file of plain functions, so a displayed number can be traced and changed in one place. |

**Where things are**

```
backend/app/db.py         tables and connection
backend/app/reference.py  manifest + reference CSV loading (idempotent)
backend/app/importer.py   validation, duplicate/conflict rules, atomic insert
backend/app/valuation.py  quantity, net cost, market value, P&L, rounding
backend/app/main.py       HTTP routes (thin)
backend/tests/            pytest suite
frontend/src/             three views: Upload, Portfolio, Position
```

**API**

| Method and path | Purpose |
|---|---|
| `GET /api/meta` | As-of date and dataset ID |
| `POST /api/imports` | Upload a trade CSV (`file` form field). 200 when imported, 422 when rejected, same body shape |
| `GET /api/portfolios` | List portfolios |
| `GET /api/portfolios/{id}` | Totals and positions for one portfolio |
| `GET /api/portfolios/{id}/positions/{instrument_id}` | One position with its trades and valuation inputs |

Interactive API docs are at http://localhost:8000/docs.

**Assumptions**

- All summaries use the manifest's `as_of` date (2026-03-27), never today's date.
- A trade price with more than four decimal places is rejected. The contract
  says prices have at most four fractional digits; I applied that to trade
  prices as well as reference prices.
- A file whose header is not exactly the seven contract columns is rejected
  with a file-level message and no row counts.
- IDs and `BUY`/`SELL` are case-sensitive, as the contract states.
- If any position in a portfolio cannot be valued (no price or FX rate on or
  before the date), the portfolio totals are shown as unavailable rather
  than as a partial sum. The contract asks for "a clear error or unavailable
  result, not a fabricated value".
- Monetary values are returned by the API as decimal strings and formatted
  as text in the browser, so no floating-point conversion happens anywhere.

## 4. Known limitations and unfinished work

- **No record of upload attempts.** The result is shown once and not stored.
  An import log (file hash, time, counts) is the first thing I would add.
- **Oversells are not detected.** The contract puts economic oversells
  outside the core exercise; a file that sold more than was held would
  produce a negative quantity.
- **The whole file is read into memory**, and existing trades are looked up
  in batches. Fine for these files; large files would need streaming and a
  background job.
- **SQLite allows one writer at a time.** Two simultaneous uploads would
  queue; under real concurrency I would move to Postgres.
- **No front-end tests.** The React code holds no business logic, and was
  checked by hand through the five-file journey.
- **Conflict messages do not say which field differs.** A conflicting row is
  reported as "already stored with different values"; showing the stored
  value beside the incoming one would make it quicker to fix.
- **Valuation re-reads price and FX series on each request.** No caching.
- **No authentication, no optional daily P&L view** (both out of scope).

## 5. Time spent and what I would prioritise next

Focused working time, approximately:

| Activity | Approx. time |
|---|---|
| Friday: reading the brief and contract, agreeing the design | 40 min |
| Saturday: backend (storage, reference loading, import rules, valuation, API) with tests | 1 h 20 min |
| Saturday: running the supplied files, hand-checking figures, error-message and test additions | 25 min |
| Saturday: front end, Docker build, five-file journey in Docker | 35 min |
| README and AI usage notes | 15 min |
| **Total** | **about 3 h 15 min** |

This was spread over Friday evening and Saturday morning rather than done in
one sitting. It does not include installing Docker and setting up a Python
environment on my machine, which I did not count as part of the exercise.

Next, in order:

1. An import log table and an "import history" list on the Upload tab.
2. An automated end-to-end test that runs the five supplied files and checks
   the counts against the manifest (today this is a manual check).
3. Conflict messages that show the stored value beside the incoming one.
4. Postgres via Compose, with the same unique key, and `NUMERIC` columns.
5. Structured logging and a health endpoint.
6. The optional daily P&L series (contract section 6).

## 6. Dataset identifier

`ds-c939fb471e09c6d8`, from `data/manifest.json` (`dataset_id`).
