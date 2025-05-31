import os
import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080")

def test_health():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_ready():
    r = requests.get(f"{BASE_URL}/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"

def test_payload():
    payload = {"numbers": [1, 2, 3, 4, 5], "text": "test text"}
    r = requests.post(f"{BASE_URL}/payload", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "numeric" in data and "text" in data
    assert data["numeric"]["min"] == 1
    assert data["numeric"]["max"] == 5
    assert data["text"]["word_count"] == 2
    assert data["text"].get("char_count", 0) == len(payload["text"])

def test_payload_bad_request():
    r = requests.post(f"{BASE_URL}/payload", json={"numbers": [], "text": ""})
    assert r.status_code in (400, 422)

def test_metrics():
    r = requests.get(f"{BASE_URL}/metrics")
    assert r.status_code == 200
    assert "payload_analyzer_request_total" in r.text
