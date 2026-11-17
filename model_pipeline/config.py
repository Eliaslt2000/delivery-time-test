"""Reads config.json and exposes the settings as constants.

All the values (paths, columns, training settings and model parameters) live in
config.json. This file only loads them, so the other modules can keep writing
`config.TARGET`, `config.CAT_COLS`, etc.
"""
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]

with open(Path(__file__).with_name("config.json")) as f:
    _cfg = json.load(f)

# Paths
DATA_PATH = ROOT_DIR / _cfg["paths"]["data"]
ARTIFACTS_DIR = ROOT_DIR / _cfg["paths"]["artifacts"]
REPORTS_DIR = ROOT_DIR / _cfg["paths"]["reports"]

# Columns
TARGET = _cfg["columns"]["target"]
ID_COL = _cfg["columns"]["id"]
NUM_COLS = _cfg["columns"]["numeric"]
CAT_COLS = _cfg["columns"]["categorical"]
FEATURES = NUM_COLS + CAT_COLS

# Valid categories (used by the API to validate the input)
CATEGORIES = _cfg["categories"]

# Training settings
RANDOM_STATE = _cfg["training"]["random_state"]
TEST_SIZE = _cfg["training"]["test_size"]
CV_FOLDS = _cfg["training"]["cv_folds"]
MISSING_LABEL = _cfg["training"]["missing_label"]

# Model that the API serves ("ridge" is the main model, "catboost" the benchmark)
PRIMARY_MODEL = _cfg["models"]["primary"]
MODEL_FILES = {name: ARTIFACTS_DIR / file for name, file in _cfg["models"]["files"].items()}
METRICS_PATH = ARTIFACTS_DIR / _cfg["models"]["metrics_file"]

# Model parameters
RIDGE_PARAMS = _cfg["models"]["ridge"]
ELASTICNET_PARAMS = _cfg["models"]["elasticnet"]
CATBOOST_PARAMS = _cfg["models"]["catboost"]
