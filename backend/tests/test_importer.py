from app.importer import import_trades

HEADER = "trade_id,portfolio_id,instrument_id,timestamp,side,quantity,price\n"
GOOD = HEADER + ("T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n"
                 "T2,P001,I001,2026-01-06T09:00:00Z,SELL,40,15\n")


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]


def test_first_upload_inserts(conn, manifest):
    result = import_trades(conn, GOOD, manifest.valuation_dates)
    assert (result.outcome, result.inserted_rows, result.skipped_rows) == ("imported", 2, 0)
    assert count(conn) == 2


def test_repeat_upload_skips_everything(conn, manifest):
    import_trades(conn, GOOD, manifest.valuation_dates)
    result = import_trades(conn, GOOD, manifest.valuation_dates)
    assert (result.inserted_rows, result.skipped_rows) == (0, 2)
    assert count(conn) == 2


def test_overlapping_upload_inserts_only_new(conn, manifest):
    import_trades(conn, GOOD, manifest.valuation_dates)
    overlap = GOOD + "T3,P001,I002,2026-01-07T09:00:00Z,BUY,5,12.5\n"
    result = import_trades(conn, overlap, manifest.valuation_dates)
    assert (result.inserted_rows, result.skipped_rows) == (1, 2)


def test_same_value_different_text_is_a_duplicate(conn, manifest):
    import_trades(conn, GOOD, manifest.valuation_dates)
    same = HEADER + "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10.0000\n"
    result = import_trades(conn, same, manifest.valuation_dates)
    assert (result.outcome, result.skipped_rows) == ("imported", 1)


def test_repeated_row_within_file_inserted_once(conn, manifest):
    line = "T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n"
    result = import_trades(conn, HEADER + line + line, manifest.valuation_dates)
    assert (result.inserted_rows, result.skipped_rows) == (1, 1)


def test_invalid_file_is_rejected_whole_and_store_unchanged(conn, manifest):
    import_trades(conn, GOOD, manifest.valuation_dates)
    bad = HEADER + ("T10,P001,I001,2026-01-07T09:00:00Z,BUY,5,10\n"      # valid -> aborted
                    "T11,P999,I001,2026-01-07T09:00:00Z,BUY,5,10\n"      # unknown portfolio
                    "T12,P001,I999,2026-01-07T09:00:00Z,BUY,5,10\n"      # unknown instrument
                    "T13,P001,I001,2026-01-07T09:00:00Z,HOLD,5,10\n"     # bad side
                    "T14,P001,I001,2026-01-07T09:00:00Z,BUY,0,10\n"      # zero quantity
                    "T15,P001,I001,2026-01-07T09:00:00Z,BUY,5,-10\n"     # negative price
                    "T16,P001,I001,07/01/2026 09:00,BUY,5,10\n"          # bad timestamp
                    "T17,P001,I001,2026-01-10T09:00:00Z,BUY,5,10\n"      # not a valuation date
                    "T18,P001,I001,2026-01-07T09:00:00Z,BUY,5,NaN\n")    # non-finite price
    result = import_trades(conn, bad, manifest.valuation_dates)
    assert result.outcome == "rejected"
    assert (result.invalid_rows, result.aborted_rows, result.total_rows) == (8, 1, 9)
    assert [e["row"] for e in result.errors] == [3, 4, 5, 6, 7, 8, 9, 10]
    assert count(conn) == 2


def test_conflict_with_stored_trade_rejects(conn, manifest):
    import_trades(conn, GOOD, manifest.valuation_dates)
    conflict = HEADER + "T1,P001,I001,2026-01-05T09:00:00Z,BUY,999,10\n"
    result = import_trades(conn, conflict, manifest.valuation_dates)
    assert (result.outcome, result.invalid_rows) == ("rejected", 1)
    assert conn.execute("SELECT quantity FROM trades WHERE trade_id='T1'").fetchone()[0] == 100


def test_conflict_within_file_marks_every_row_of_that_id(conn, manifest):
    text = HEADER + ("T1,P001,I001,2026-01-05T09:00:00Z,BUY,100,10\n"
                     "T1,P001,I001,2026-01-05T09:00:00Z,BUY,200,10\n"
                     "T2,P001,I001,2026-01-06T09:00:00Z,SELL,40,15\n")
    result = import_trades(conn, text, manifest.valuation_dates)
    assert (result.invalid_rows, result.aborted_rows) == (2, 1)
    assert count(conn) == 0


def test_wrong_header_is_a_file_level_error(conn, manifest):
    result = import_trades(conn, "id,qty\nT1,5\n", manifest.valuation_dates)
    assert result.outcome == "rejected" and result.file_error
