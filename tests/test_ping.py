def test_ping_returns_row_count_from_database(client):
    first = client.post("/api/ping")
    second = client.post("/api/ping")

    assert first.status_code == 200
    assert first.json()["count"] == 1
    assert second.json()["count"] == 2


def test_each_test_starts_with_empty_database(client):
    assert client.post("/api/ping").json()["count"] == 1


def test_migration_enabled_pgvector(db):
    row = db.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'").fetchone()

    assert row is not None

