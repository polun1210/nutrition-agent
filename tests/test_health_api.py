def test_health_returns_ok_without_login(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_access_database_or_storage(client, app, monkeypatch):
    from nutrition_agent.api.deps import get_connection, get_photo_store

    def unavailable(*args, **kwargs):
        raise AssertionError("健康檢查不應存取資料庫或物件儲存")

    app.dependency_overrides[get_connection] = unavailable
    app.dependency_overrides[get_photo_store] = unavailable
    monkeypatch.setattr("psycopg.connect", unavailable)
    monkeypatch.setattr("botocore.client.BaseClient._make_api_call", unavailable)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
