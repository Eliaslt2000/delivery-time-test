# Next steps (Part III: API prototype)

## What is built
- app/model_results.py: a FastAPI service with /health, /model-info, /predict and /predict/batch.
- Input validation (types, ranges and allowed categories), optional fields imputed as in training, and warnings when the input is outside the training range.
- 8 tests for the API in tests/test_api.py (15 tests in total with the pipeline tests).
- Setup and usage in app/README.md.

## What I would do next
1. **Container and CI.** A Dockerfile and a GitHub Actions workflow that runs the tests on every pull request. I did not build them, so they are not in this repo.
2. **Better error information.** Return a range and not only one number, because the error grows with the distance (MAE 3.9 min up to 5 km and 8.6 min from 15 to 20 km).
3. **Model improvements.** Test a Weather x Traffic_Level interaction and tune CatBoost with a small search. Both are in reports/error_insights.md and reports/model_notes.md as untested ideas.
4. **Monitoring.** Log the inputs and the predictions, compare them with the real delivery time when it arrives, and watch the drift of the inputs.
5. **Security and versioning.** Authentication, rate limits and a model version in the response.

The full production plan is in strategic_reflections.md (question 5).
