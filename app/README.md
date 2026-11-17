# Delivery Time API

A FastAPI service that returns the estimated delivery time (minutes) with the trained Ridge model. The code is in model_results.py.

## Setup and run
From the project root, with the virtual environment active and pip install -r requirements.txt done:
```bash
uvicorn app.model_results:app --reload
```
The service loads the model from model_pipeline/artifacts/ when it starts. If the folder is empty, run python -m model_pipeline.train first. The interactive documentation is at http://127.0.0.1:8000/docs.

## Endpoints
| Endpoint | What it does |
|---|---|
| GET /health | Checks that the service is up and shows the loaded model. |
| GET /model-info | Model name, features, test metrics and the CV table. |
| POST /predict | Estimates the time of one delivery. |
| POST /predict/batch | Estimates up to 1000 deliveries in one call. |

## Request fields
| Field | Required | Allowed values |
|---|---|---|
| distance_km | yes | greater than 0, up to 100 |
| preparation_time_min | yes | 0 to 180 |
| vehicle_type | yes | Bike, Scooter, Car |
| weather | no | Clear, Windy, Foggy, Rainy, Snowy |
| traffic_level | no | Low, Medium, High |
| time_of_day | no | Morning, Afternoon, Evening, Night |
| courier_experience_yrs | no | 0 to 50 |

Optional fields can be left out: the model fills them in the same way as in training. Invalid values (for example "weather": "Sunny" or a negative distance) return a 422 error.

## Example
```bash
curl -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"distance_km": 8.5, "preparation_time_min": 15, "vehicle_type": "Bike",
       "weather": "Rainy", "traffic_level": "High", "time_of_day": "Evening",
       "courier_experience_yrs": 3}'
```
Response:
```json
{
  "estimated_delivery_time_min": 60.8,
  "typical_error_min": 5.9,
  "model": "ridge",
  "warnings": []
}
```
With only the required fields (distance_km 5, preparation_time_min 10, vehicle_type Car) the answer is 39.3 min and a warning says which fields were imputed.

Batch:
```bash
curl -X POST http://127.0.0.1:8000/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"deliveries": [{"distance_km": 8.5, "preparation_time_min": 15, "vehicle_type": "Bike"},
                      {"distance_km": 2, "preparation_time_min": 15, "vehicle_type": "Bike"}]}'
```
It returns `estimated_delivery_times_min` in the same order.

## What the response means
- estimated_delivery_time_min: the estimate, rounded to 1 decimal and never below 0.
- typical_error_min: the MAE of the model on the test set (about 6 min). It is an average: the error is smaller for short trips and larger for long ones.
- warnings: the input is outside the range seen in training (distance 0.5 to 20 km, preparation 5 to 29 min), so the answer is an extrapolation, or some optional fields were imputed.

## Tests
```bash
python -m pytest tests/test_api.py -q
```

## Limits
No authentication, no logging, and one model loaded from files. It is a prototype. See next_steps.md for what I would add.
