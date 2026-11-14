from app import reference


def test_reference_rows_loaded(conn):
    assert conn.execute("SELECT COUNT(*) FROM instruments").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 5


def test_reloading_does_not_duplicate(conn, data_dir):
    reference.load_reference(conn, data_dir)  # simulates an app restart
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 5
    assert conn.execute("SELECT COUNT(*) FROM fx_rates").fetchone()[0] == 3
