"""Training: cross-validated comparison of the candidate models and final evaluation.
"""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_validate
from model_pipeline import config
from model_pipeline.preprocessing import load_data, split_data
from model_pipeline.regression_model import build_catboost, build_ridge, candidate_models


def cross_validate_models(X_train, y_train) -> pd.DataFrame:
    """5-fold CV on the training set. Imputation is fitted inside each fold."""
    cv = KFold(n_splits=config.CV_FOLDS, shuffle=True, random_state=config.RANDOM_STATE)
    scoring = {
        "rmse": "neg_root_mean_squared_error",
        "mae": "neg_mean_absolute_error",
        "r2": "r2",
    }
    rows = []
    for name, model in candidate_models().items():
        scores = cross_validate(model, X_train, y_train, cv=cv, scoring=scoring)
        rows.append(
            {
                "model": name,
                "rmse_mean": -scores["test_rmse"].mean(),
                "rmse_std": scores["test_rmse"].std(),
                "mae_mean": -scores["test_mae"].mean(),
                "mae_std": scores["test_mae"].std(),
                "r2_mean": scores["test_r2"].mean(),
                "r2_std": scores["test_r2"].std(),
            }
        )
    return pd.DataFrame(rows).sort_values("rmse_mean").reset_index(drop=True)


def evaluate(model, X, y) -> dict:
    """RMSE, MAE and R2 of a fitted model."""
    pred = model.predict(X)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, pred))),
        "mae": float(mean_absolute_error(y, pred)),
        "r2": float(r2_score(y, pred)),
    }


def main():
    config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_data()
    X_train, X_test, y_train, y_test = split_data(df)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    # Cross-validated comparison (train set only)
    cv_results = cross_validate_models(X_train, y_train)
    cv_results.round(4).to_csv(config.REPORTS_DIR / "cv_results.csv", index=False)
    print("\nCross-validation results (5-fold, train set):")
    print(cv_results.round(3).to_string(index=False))

    # Final model selection 
    final_models = {"ridge": build_ridge("missing"), "catboost": build_catboost()}
    metrics = {"cv": cv_results.round(4).to_dict(orient="records"), "test": {}}
    for name, model in final_models.items():
        model.fit(X_train, y_train)
        metrics["test"][name] = evaluate(model, X_test, y_test)
        joblib.dump(model, config.MODEL_FILES[name])
        print(f"\nTest metrics ({name}): {metrics['test'][name]}")

    ridge_alpha = float(final_models["ridge"].named_steps["model"].alpha_)
    metrics["ridge_alpha"] = ridge_alpha
    metrics["n_train"] = int(len(X_train))
    metrics["n_test"] = int(len(X_test))
    with open(config.METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved models and metrics in {config.ARTIFACTS_DIR}")


if __name__ == "__main__":
    main()
