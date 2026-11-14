# AI usage

## Tools used

- Claude (Anthropic), in chat. No other AI tools, and no AI coding agent
  with access to the repository.

## Main tasks delegated

- **Design discussion.** After reading the brief and the data contract
  myself, I had Claude read them too and we compared approaches for each
  layer (web framework, UI, storage, tests, run command) and their
  trade-offs before any code was written.
- **Backend drafts.** Once the shape was agreed (five modules: storage,
  reference loading, import rules, valuation, routes), Claude drafted each
  module and its pytest tests from the contract's rules. I built the project
  up from those drafts one file at a time, running the tests at each step.
- **Front end.** Delegated in full, to a specification I set: three views
  (Upload, Portfolio, Position), tables only, no business logic in the
  browser, money handled as text and never as a JavaScript number. I wanted
  my own time on the backend, which is the role I am applying for.
- **Docker.** The Dockerfile and Compose file.
- **Debugging help.** Working through environment problems on my machine:
  packages installed into the wrong Python environment, an old pytest that
  does not run on Python 3.11, and the development proxy not reaching the
  backend.
- **README structure.**

## Material decisions or code influenced

**Mine**

- React and Docker Compose, overriding the simpler stack Claude first
  proposed (see "One suggestion I rejected").
- Every validation message must show the value it rejected. The drafted
  messages did this for some rules and not others ("price must be a positive
  decimal number" with no value). I made them consistent and added a test.
- Asking which of the contract's financial conventions had no test. That
  produced four more tests: missing price, missing trade-day FX, trades after
  the valuation date, and totals summed before rounding.
- Pinning `requirements.txt` to the versions in my own environment rather
  than the ones suggested.

**Shaped by AI, and accepted after review**

- SQLite instead of Postgres. For one user uploading a few hundred rows by
  hand it needs no setup and survives a restart; Postgres is what I would
  move to for concurrent writers.
- The importer's three steps: check each row, then check rows against each
  other and against stored trades, then write in one transaction.
- A frozen dataclass for a parsed trade, so that the contract's "exact
  duplicate" is plain equality on parsed values.
- Serving the built React app from the FastAPI process, so there is one
  container and one port.

## Verification

- **Tests.** The contract's three worked examples are tests and pass (640,
  100 and 20 GBP), with tests for each import rule and the edge cases above.
- **The supplied files, in the contract's order,** first against the local
  server and then in Docker through the UI: 600 inserted; 0 inserted and 600
  skipped; 60 inserted; rejected with 8 invalid and 2 aborted; 10 inserted.
- **The rejected file, reason by reason.** I read each of the 8 reasons
  against its row: a conflict with a stored trade, an unknown portfolio, a
  negative price, an unknown instrument, a date that is not a valuation date,
  an invalid side, a zero quantity and a malformed timestamp.
- **One position by hand.** ZZOTT02 in P002: the eight signed costs sum to
  GBP 171,920.60; 762 x 220.8576 = GBP 168,293.49; P&L = -GBP 3,627.11. All
  three match the screen. Two market values in P001 were checked the same way.
- **Contract behaviours seen on the real data:** a closed position with zero
  value and non-zero P&L (ZZLUM03 in P001), and a carried-forward price
  flagged with its date while FX stays at the valuation date (ZZCAR12).

**One suggestion I rejected.** Claude's first proposal was server-rendered
HTML pages (Jinja) with a plain Python start command and no Docker, as the
fastest option for three hours. I rejected it after reading
`DATA_CONTRACT.md`, which says uploads "must enter through the React upload
flow" and that reference loading is "invoked by Compose". The pack's own
README also says the trade files are for "your React UI".

**One thing I corrected.** The drafted error messages did not all show the
offending value. I changed them so each one does, for example
"quantity must be a positive whole number, got '0'".

**One thing the tests caught in an AI draft.** The first draft of the API
failed its own tests with a SQLite threading error, because a connection
opened for a request could be used on a different worker thread. It was
fixed by giving each request its own connection.

## Time and remaining work

- About 3 hours on Friday reading the brief and contract, discussing the
  design and setting up my environment, then one build session of about
  2 h 40 min on Saturday morning, plus about 30 minutes on documentation.
  This is longer than the suggested three hours; the extra went on
  understanding the financial conventions and on environment setup.
- Not built: the optional daily P&L (contract section 6), an import history,
  and an automated end-to-end test on the supplied files.
- Next priorities are listed in `README.md`, section 5.
