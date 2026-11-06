import nutrition_agent


def test_package_imports():
    assert nutrition_agent.__doc__


def test_ping_端點已移除(client):
    assert client.post("/api/ping").status_code in (404, 405)
