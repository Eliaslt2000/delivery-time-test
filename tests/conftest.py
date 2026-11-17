"""Shared test setup: make sure the trained model exists before the tests run."""
import pytest

from model_pipeline import config
from model_pipeline.train import main as train_main


@pytest.fixture(scope="session", autouse=True)
def trained_model():
    if not config.MODEL_FILES[config.PRIMARY_MODEL].exists():
        train_main()
