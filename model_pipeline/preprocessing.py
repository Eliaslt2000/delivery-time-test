"""Data loading, train/test split and preprocessing steps.

All the imputation is done inside scikit-learn pipelines, so it is fitted on the
training folds only (no leakage from the validation or test rows).
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from model_pipeline import config


def load_data(path=config.DATA_PATH) -> pd.DataFrame:
    """Read the raw CSV."""
    return pd.read_csv(path)


def split_data(df: pd.DataFrame):
    """Hold out a test set. The test set is only used once, at the end."""
    X = df[config.FEATURES]
    y = df[config.TARGET]
    return train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE
    )


class FillCategoricalMissing(BaseEstimator, TransformerMixin):
    """Fill the missing values of the categorical columns with a 'Missing' category.

    Returns a DataFrame, so it can be used before CatBoost.
    """

    def __init__(self, columns=None, label=config.MISSING_LABEL):
        self.columns = columns
        self.label = label

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        X = X.copy()
        columns = self.columns if self.columns is not None else config.CAT_COLS
        for col in columns:
            X[col] = X[col].fillna(self.label).astype(str)
        return X


class RandomSampleImputer(BaseEstimator, TransformerMixin):
    """Fill the missing values with a random draw of the observed values of the column.
    It keeps the category proportions of the training data. The draw uses a fixed
    seed, so the results can be reproduced.
    """

    def __init__(self, random_state=config.RANDOM_STATE):
        self.random_state = random_state

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.columns_ = list(X.columns)
        self.observed_ = {col: X[col].dropna().to_numpy() for col in self.columns_}
        return self

    def transform(self, X):
        X = pd.DataFrame(X, columns=self.columns_).copy()
        rng = np.random.default_rng(self.random_state)
        for col in self.columns_:
            mask = X[col].isna()
            if mask.any():
                X.loc[mask, col] = rng.choice(self.observed_[col], size=int(mask.sum()))
        return X.astype(object)

    def get_feature_names_out(self, input_features=None):
        return np.array(self.columns_)


def _categorical_imputer(strategy: str):
    """Imputer for the categorical columns: 'missing', 'most_frequent' or 'random'."""
    if strategy == "missing":
        return SimpleImputer(strategy="constant", fill_value=config.MISSING_LABEL)
    if strategy == "most_frequent":
        return SimpleImputer(strategy="most_frequent")
    if strategy == "random":
        return RandomSampleImputer()
    raise ValueError(f"Unknown categorical strategy: {strategy}")


def build_preprocessor(cat_strategy: str = "missing") -> ColumnTransformer:
    """Preprocessing for the linear models.

    Numeric: median imputation + scaling.
    Categorical: imputation (cat_strategy) + one-hot encoding.
    """
    numeric = Pipeline(
        [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
    )
    categorical = Pipeline(
        [
            ("imputer", _categorical_imputer(cat_strategy)),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        [("num", numeric, config.NUM_COLS), ("cat", categorical, config.CAT_COLS)]
    )
