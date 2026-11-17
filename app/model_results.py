"""FastAPI service that returns the estimated delivery time.

Run from the project root:
    uvicorn app.model_results:app --reload
Then open http://127.0.0.1:8000/docs
"""
import json
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from model_pipeline import config
from model_pipeline.predict import load_model, predict_batch

# Range of the training data: outside it the model extrapolates and is less reliable
TRAIN_RANGE = {"distance_km": (0.5, 20.0), "preparation_time_min": (5, 29)}


class DeliveryRequest(BaseModel):
    """Details of one delivery. Optional fields can be left out: the model
    imputes them in the same way as in training."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "distance_km": 8.5,
                "preparation_time_min": 15,
                "vehicle_type": "Bike",
                "weather": "Rainy",
                "traffic_level": "High",
                "time_of_day": "Evening",
                "courier_experience_yrs": 3,
            }
        }
    )

    distance_km: float = Field(gt=0, le=100, description="Distance of the delivery in km")
    preparation_time_min: float = Field(ge=0, le=180, description="Restaurant preparation time in minutes")
    vehicle_type: Literal["Bike", "Scooter", "Car"]
    weather: Optional[Literal["Clear", "Windy", "Foggy", "Rainy", "Snowy"]] = None
    traffic_level: Optional[Literal["Low", "Medium", "High"]] = None
    time_of_day: Optional[Literal["Morning", "Afternoon", "Evening", "Night"]] = None
    courier_experience_yrs: Optional[float] = Field(default=None, ge=0, le=50)


class PredictionResponse(BaseModel):
    estimated_delivery_time_min: float
    typical_error_min: float = Field(description="Mean absolute error of the model on the test set")
    model: str
    warnings: List[str] = []


class BatchRequest(BaseModel):
    deliveries: List[DeliveryRequest] = Field(min_length=1, max_length=1000)


class BatchResponse(BaseModel):
    estimated_delivery_times_min: List[float]
    model: str


def to_model_record(item: DeliveryRequest) -> dict:
    """Translate the API field names to the column names used in training."""
    return {
        "Distance_km": item.distance_km,
        "Preparation_Time_min": item.preparation_time_min,
        "Vehicle_Type": item.vehicle_type,
        "Weather": item.weather,
        "Traffic_Level": item.traffic_level,
        "Time_of_Day": item.time_of_day,
        "Courier_Experience_yrs": item.courier_experience_yrs,
    }


def input_warnings(item: DeliveryRequest) -> List[str]:
    """Warn when the input is outside the range seen in training or has missing fields."""
    warnings = []
    for field, (low, high) in TRAIN_RANGE.items():
        value = getattr(item, field)
        if value < low or value > high:
            warnings.append(
                f"{field}={value} is outside the training range ({low} to {high}); "
                "the estimate is an extrapolation."
            )
    missing = [
        name
        for name in ["weather", "traffic_level", "time_of_day", "courier_experience_yrs"]
        if getattr(item, name) is None
    ]
    if missing:
        warnings.append(f"Missing fields imputed by the model: {', '.join(missing)}.")
    return warnings


def read_metrics() -> dict:
    if not config.METRICS_PATH.exists():
        return {}
    with open(config.METRICS_PATH) as f:
        return json.load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model once, when the service starts."""
    app.state.model_name = config.PRIMARY_MODEL
    app.state.model = load_model(app.state.model_name)
    metrics = read_metrics()
    app.state.typical_error = metrics.get("test", {}).get(app.state.model_name, {}).get("mae", float("nan"))
    yield


app = FastAPI(
    title="Delivery Time Estimator",
    description="Estimates the delivery time (minutes) of a food delivery.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    """Check that the service is up and the model is loaded."""
    return {"status": "ok", "model": app.state.model_name}


@app.get("/model-info")
def model_info():
    """Metrics and features of the served model."""
    metrics = read_metrics()
    return {
        "model": app.state.model_name,
        "features": config.FEATURES,
        "test_metrics": metrics.get("test", {}).get(app.state.model_name, {}),
        "cv_results": metrics.get("cv", []),
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(item: DeliveryRequest):
    """Estimate the delivery time of one delivery."""
    try:
        value = float(predict_batch([to_model_record(item)], app.state.model_name)[0])
    except Exception as error:  # the model should never fail with a validated input
        raise HTTPException(status_code=500, detail=f"Prediction failed: {error}")
    return PredictionResponse(
        estimated_delivery_time_min=round(max(value, 0.0), 1),
        typical_error_min=round(float(app.state.typical_error), 1),
        model=app.state.model_name,
        warnings=input_warnings(item),
    )


@app.post("/predict/batch", response_model=BatchResponse)
def predict_many(batch: BatchRequest):
    """Estimate the delivery time of several deliveries at once."""
    records = [to_model_record(item) for item in batch.deliveries]
    values = np.clip(predict_batch(records, app.state.model_name), 0, None)
    return BatchResponse(
        estimated_delivery_times_min=[round(float(v), 1) for v in values],
        model=app.state.model_name,
    )
