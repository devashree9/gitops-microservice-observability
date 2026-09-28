from fastapi.testclient import TestClient
from main import app, r

client = TestClient(app)


def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "GitOps Microservice"}


def test_set_and_get_cache():
    response = client.post("/cache/testkey/testvalue")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "key": "testkey", "value": "testvalue"}

    response = client.get("/cache/testkey")
    assert response.status_code == 200
    assert response.json() == {"key": "testkey", "value": "testvalue"}


def test_get_missing_key_returns_404():
    response = client.get("/cache/definitely_not_a_real_key")
    assert response.status_code == 404


def test_compute_returns_result_and_caches_it():
    r.delete("compute:5")  # start from a cold cache so reruns are deterministic
    response = client.get("/compute/5")
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 5
    assert body["result"] == sum(i * i for i in range(5))
    assert body["source"] == "computed"

    # second call within TTL should hit the cache
    response = client.get("/compute/5")
    body = response.json()
    assert body["source"] == "cache"


def test_compute_rejects_invalid_input():
    response = client.get("/compute/-1")
    assert response.status_code == 400

    response = client.get("/compute/999999")
    assert response.status_code == 400
