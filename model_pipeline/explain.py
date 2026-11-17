"""Explainability helpers: coefficients, permutation importance and CatBoost SHAP values."""
import numpy as np
import pandas as pd
from catboost import Pool
from sklearn.inspection import permutation_importance

from model_pipeline import config


def linear_coefficients(ridge_pipeline) -> pd.DataFrame:
    """Coefficients of the Ridge model, in minutes per one standard deviation
    (numeric columns are scaled) or per category (one-hot columns)."""
    names = ridge_pipeline.named_steps["preprocess"].get_feature_names_out()
    coefs = ridge_pipeline.named_steps["model"].coef_
    out = pd.DataFrame({"feature": names, "coefficient": coefs})
    out["abs_coefficient"] = out["coefficient"].abs()
    return out.sort_values("abs_coefficient", ascending=False).reset_index(drop=True)


def permutation_table(model, X_test, y_test, n_repeats: int = 30) -> pd.DataFrame:
    """Increase in RMSE when one original column is shuffled."""
    result = permutation_importance(
        model,
        X_test,
        y_test,
        scoring="neg_root_mean_squared_error",
        n_repeats=n_repeats,
        random_state=config.RANDOM_STATE,
    )
    out = pd.DataFrame(
        {
            "feature": X_test.columns,
            "rmse_increase_mean": result.importances_mean,
            "rmse_increase_std": result.importances_std,
        }
    )
    return out.sort_values("rmse_increase_mean", ascending=False).reset_index(drop=True)


def catboost_shap(catboost_pipeline, X) -> pd.DataFrame:
    """Mean absolute SHAP value per column (minutes), using CatBoost's built-in SHAP."""
    X_ready = catboost_pipeline.named_steps["fill_cat"].transform(X)
    booster = catboost_pipeline.named_steps["model"].model_
    pool = Pool(X_ready, cat_features=config.CAT_COLS)
    shap_values = booster.get_feature_importance(pool, type="ShapValues")[:, :-1]
    out = pd.DataFrame(
        {"feature": X_ready.columns, "mean_abs_shap": np.abs(shap_values).mean(axis=0)}
    )
    return out.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
