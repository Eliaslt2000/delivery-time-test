import numpy as np
import pandas as pd

from model_pipeline import config
from model_pipeline.preprocessing import (
    RandomSampleImputer,
    build_preprocessor,
    load_data,
    split_data,
)
from model_pipeline.predict import predict_batch, predict_one


def test_data_has_expected_columns():
    df = load_data()
    assert df.shape == (1000, 9)
    assert set(config.FEATURES + [config.TARGET]).issubset(df.columns)


def test_split_sizes():
    X_train, X_test, y_train, y_test = split_data(load_data())
    assert len(X_train) == 800 and len(X_test) == 200
    assert list(X_train.columns) == config.FEATURES


def test_preprocessor_output_has_no_missing_values():
    X_train, _, _, _ = split_data(load_data())
    for strategy in ["missing", "most_frequent", "random"]:
        out = build_preprocessor(strategy).fit_transform(X_train)
        assert not np.isnan(out.toarray() if hasattr(out, "toarray") else out).any()


def test_random_imputer_keeps_only_observed_values():
    df = pd.DataFrame({"a": ["x", "y", None, "x", None]})
    out = RandomSampleImputer().fit(df).transform(df)
    assert out["a"].isna().sum() == 0
    assert set(out["a"]) <= {"x", "y"}


def test_predict_one_returns_a_plausible_number():
    record = {
        "Distance_km": 8.5, "Preparation_Time_min": 15, "Vehicle_Type": "Bike",
        "Weather": "Rainy", "Traffic_Level": "High", "Time_of_Day": "Evening",
        "Courier_Experience_yrs": 3,
    }
    assert 10 < predict_one(record) < 150


def test_predict_handles_missing_optional_fields():
    value = predict_one({"Distance_km": 5, "Preparation_Time_min": 10, "Vehicle_Type": "Car"})
    assert np.isfinite(value)


def test_longer_distance_means_longer_time():
    base = {"Preparation_Time_min": 15, "Vehicle_Type": "Bike", "Weather": "Clear",
            "Traffic_Level": "Low", "Time_of_Day": "Morning", "Courier_Experience_yrs": 4}
    short, long_ = predict_batch([{**base, "Distance_km": 2}, {**base, "Distance_km": 18}])
    assert long_ > short + 20
