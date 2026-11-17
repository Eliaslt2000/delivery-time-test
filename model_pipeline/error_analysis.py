"""Error analysis helpers"""
import numpy as np
import pandas as pd
from model_pipeline import config

def build_error_frame(model, X, y) -> pd.DataFrame:
    """Features + real time + prediction + residual (real - predicted).
    A positive residual means the model UNDERESTIMATES the delivery time.
    """
    out = X.copy()
    out["actual"] = y.to_numpy()
    out["predicted"] = model.predict(X)
    out["residual"] = out["actual"] - out["predicted"]
    out["abs_error"] = out["residual"].abs()
    out["distance_band"] = pd.cut(
        out["Distance_km"], bins=[0, 5, 10, 15, 20], labels=["0-5", "5-10", "10-15", "15-20"]
    )
    return out


def error_by_group(errors: pd.DataFrame, column: str) -> pd.DataFrame:
    """Bias (mean residual), MAE and size of each group of one column.
    The missing values are shown as their own group.
    """
    grouped = errors.assign(**{column: errors[column].astype(object).fillna(config.MISSING_LABEL)})
    table = grouped.groupby(column, observed=True).agg(
        n=("residual", "size"),
        bias_min=("residual", "mean"),
        mae_min=("abs_error", "mean"),
        share_underestimated=("residual", lambda r: float((r > 0).mean())),
    )
    return table.round(2).sort_values("mae_min", ascending=False)


def all_group_tables(errors: pd.DataFrame) -> dict:
    """Error tables for every categorical column and for the distance bands."""
    columns = config.CAT_COLS + ["distance_band"]
    return {col: error_by_group(errors, col) for col in columns}


def worst_cases(errors: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """The n predictions with the largest absolute error."""
    cols = config.FEATURES + ["actual", "predicted", "residual"]
    return errors.sort_values("abs_error", ascending=False).head(n)[cols].round(1)


def interaction_table(errors: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    """Mean residual for the combinations of two categorical columns
    (for example Weather x Traffic_Level), to look for interactions the linear model misses."""
    table = errors.pivot_table(index=a, columns=b, values="residual", aggfunc="mean")
    return table.round(1)


def error_summary(errors: pd.DataFrame) -> dict:
    """Global error numbers."""
    return {
        "rmse": float(np.sqrt((errors["residual"] ** 2).mean())),
        "mae": float(errors["abs_error"].mean()),
        "bias": float(errors["residual"].mean()),
        "share_error_over_10_min": float((errors["abs_error"] > 10).mean()),
        "share_underestimated": float((errors["residual"] > 0).mean()),
    }
