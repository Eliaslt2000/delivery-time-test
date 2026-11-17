"""Prediction with a trained model.
"""
import argparse
import json
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from model_pipeline import config


@lru_cache(maxsize=None)
def load_model(name: str = config.PRIMARY_MODEL):
    """Load a trained pipeline from the artifacts folder."""
    path = config.MODEL_FILES[name]
    if not path.exists():
        raise FileNotFoundError(
            f"Model file not found: {path}. Run th script 'model_pipeline\train.py' first."
        )
    return joblib.load(path)


def to_frame(records) -> pd.DataFrame:
    """Build the input frame with the exact columns the model expects.

    Missing columns or values become NaN, and the pipeline imputes them
    in the same way as in training.
    """
    df = pd.DataFrame(records)
    for col in config.FEATURES:
        if col not in df.columns:
            df[col] = np.nan
    return df[config.FEATURES]


def predict_batch(records, model_name: str = config.PRIMARY_MODEL) -> np.ndarray:
    """Predict the delivery time (minutes) for a list of dicts or a DataFrame."""
    model = load_model(model_name)
    return model.predict(to_frame(records))


def predict_one(record: dict, model_name: str = config.PRIMARY_MODEL) -> float:
    """Predict the delivery time (minutes) for one delivery."""
    return float(predict_batch([record], model_name)[0])


def main():
    parser = argparse.ArgumentParser(description="Predict delivery time in minutes.")
    parser.add_argument("--json", help="One delivery as a JSON string.")
    parser.add_argument("--csv", help="CSV file with several deliveries.")
    parser.add_argument("--output", help="Where to save the predictions (CSV).")
    parser.add_argument("--model", default=config.PRIMARY_MODEL, choices=list(config.MODEL_FILES))
    args = parser.parse_args()

    if args.json:
        value = predict_one(json.loads(args.json), args.model)
        print(f"Estimated delivery time: {value:.1f} min")
    elif args.csv:
        df = pd.read_csv(args.csv)
        df["Predicted_Delivery_Time_min"] = predict_batch(df, args.model).round(1)
        if args.output:
            df.to_csv(args.output, index=False)
            print(f"Saved {len(df)} predictions in {args.output}")
        else:
            print(df.head())
    else:
        parser.error("Use --json or --csv.")


if __name__ == "__main__":
    main()
