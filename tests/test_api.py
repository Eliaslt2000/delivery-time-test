from fastapi.testclient import TestClient

from app.model_results import app

VALID = {
    "distance_km": 8.5,
    "preparation_time_min": 15,
    "vehicle_type": "Bike",
    "weather": "Rainy",
    "traffic_level": "High",
    "time_of_day": "Evening",
    "courier_experience_yrs": 3,
}


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_predict_valid_request():
    with TestClient(app) as client:
        response = client.post("/predict", json=VALID)
    body = response.json()
    assert response.status_code == 200
    assert 10 < body["estimated_delivery_time_min"] < 150
    assert body["warnings"] == []


def test_predict_with_only_required_fields():
    payload = {"distance_km": 5, "preparation_time_min": 10, "vehicle_type": "Car"}
    with TestClient(app) as client:
        response = client.post("/predict", json=payload)
    assert response.status_code == 200
    assert "imputed" in response.json()["warnings"][0]


def test_predict_warns_outside_training_range():
    with TestClient(app) as client:
        response = client.post("/predict", json={**VALID, "distance_km": 45})
    assert response.status_code == 200
    assert any("extrapolation" in w for w in response.json()["warnings"])


def test_invalid_category_is_rejected():
    with TestClient(app) as client:
        response = client.post("/predict", json={**VALID, "weather": "Sunny"})
    assert response.status_code == 422


def test_negative_distance_is_rejected():
    with TestClient(app) as client:
        response = client.post("/predict", json={**VALID, "distance_km": -3})
    assert response.status_code == 422


def test_batch_prediction():
    with TestClient(app) as client:
        response = client.post("/predict/batch", json={"deliveries": [VALID, {**VALID, "distance_km": 2}]})
    values = response.json()["estimated_delivery_times_min"]
    assert response.status_code == 200 and len(values) == 2 and values[0] > values[1]


def test_model_info():
    with TestClient(app) as client:
        response = client.get("/model-info")
    assert response.status_code == 200
    assert "r2" in response.json()["test_metrics"]
