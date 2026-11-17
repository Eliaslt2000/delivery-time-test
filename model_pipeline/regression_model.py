"""The regression models: Ridge (main), ElasticNet, CatBoost (benchmark) and the baseline.

The parameters come from config.json. 
The CatBoost wrapper lives here (and not intrain.py) so the saved model files can be loaded from any script.
"""
import numpy as np
from catboost import CatBoostRegressor
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import ElasticNetCV, RidgeCV
from sklearn.pipeline import Pipeline
from model_pipeline import config
from model_pipeline.preprocessing import FillCategoricalMissing, build_preprocessor


class CatBoostModel(RegressorMixin, BaseEstimator):
    """Thin wrapper around CatBoostRegressor.
    """

    def __init__(self, iterations=config.CATBOOST_PARAMS["iterations"],
                 learning_rate=config.CATBOOST_PARAMS["learning_rate"],
                 depth=config.CATBOOST_PARAMS["depth"],
                 l2_leaf_reg=config.CATBOOST_PARAMS["l2_leaf_reg"],
                 random_seed=config.RANDOM_STATE):
        self.iterations = iterations
        self.learning_rate = learning_rate
        self.depth = depth
        self.l2_leaf_reg = l2_leaf_reg
        self.random_seed = random_seed

    def fit(self, X, y):
        self.model_ = CatBoostRegressor(
            iterations=self.iterations,
            learning_rate=self.learning_rate,
            depth=self.depth,
            l2_leaf_reg=self.l2_leaf_reg,
            cat_features=config.CAT_COLS,
            random_seed=self.random_seed,
            verbose=0,
            allow_writing_files=False,
        )
        self.model_.fit(X, y)
        self.feature_names_in_ = np.array(X.columns)
        return self

    def predict(self, X):
        return self.model_.predict(X)


def build_ridge(cat_strategy: str = "missing") -> Pipeline:
    """Main model: Ridge regression."""
    return Pipeline(
        [
            ("preprocess", build_preprocessor(cat_strategy)),
            ("model", RidgeCV(alphas=np.logspace(*config.RIDGE_PARAMS["alphas_logspace"]))),
        ]
    )


def build_elasticnet(cat_strategy: str = "missing") -> Pipeline:
    """Regularized linear model that can also set coefficients to zero (feature selection)."""
    return Pipeline(
        [
            ("preprocess", build_preprocessor(cat_strategy)),
            (
                "model",
                ElasticNetCV(random_state=config.RANDOM_STATE, **config.ELASTICNET_PARAMS),
            ),
        ]
    )


def build_catboost() -> Pipeline:
    """Benchmark: CatBoost"""
    return Pipeline(
        [
            ("fill_cat", FillCategoricalMissing()),
            ("model", CatBoostModel()),
        ]
    )


def build_baseline() -> Pipeline:
    """Reference model always predicts the mean of the training target."""
    return Pipeline(
        [("preprocess", build_preprocessor("missing")), ("model", DummyRegressor())]
    )


def candidate_models() -> dict:
    """All the models that are compared with cross-validation."""
    return {
        "baseline_mean": build_baseline(),
        "ridge_missing": build_ridge("missing"),
        "ridge_most_frequent": build_ridge("most_frequent"),
        "ridge_random": build_ridge("random"),
        "elasticnet_missing": build_elasticnet("missing"),
        "catboost": build_catboost(),
    }
