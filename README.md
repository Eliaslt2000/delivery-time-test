# Delivery Time Prediction

Predicts the delivery time (minutes) of a food delivery from the distance, the preparation time, the weather, the traffic and other order details. It also includes the SQL analysis, the EDA and the error analysis, and an API prototype.

## Structure
```
data/raw/Food_Delivery_Times.csv   Kaggle dataset (downloaded manually, not with the Kaggle API)
sql/                               Part I: sql_queries.sql (Q1-Q5) and sql_insights.md
notebooks/                         EDA.ipynb and model_training.ipynb
reports/                           EDA_report.md, model_notes.md, explainability.md,
                                   error_insights.md, cv_results.csv and figures/
model_pipeline/                    config.json (parameters) and config.py (loader), preprocessing,
                                   regression_model (the models), train, predict, explain,
                                   error_analysis, and artifacts/ (saved models and metrics)
app/                               model_results.py (FastAPI) and README.md (API usage)
tests/                             pytest tests for the pipeline and the API
strategic_reflections.md           Part II, strategic questions
next_steps.md                      Part III notes
requirements.txt
```

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
I used Python 3.14.4. The versions are pinned in requirements.txt.

## Run
**Train** (compares the models with 5-fold CV, then saves the models and the metrics in model_pipeline/artifacts/ and the CV table in reports/cv_results.csv):
```bash
python -m model_pipeline.train
```
**Predict** from the command line:
```bash
python -m model_pipeline.predict --json '{"Distance_km": 8.5, "Weather": "Rainy", "Traffic_Level": "High", "Time_of_Day": "Evening", "Vehicle_Type": "Bike", "Preparation_Time_min": 15, "Courier_Experience_yrs": 3}'
python -m model_pipeline.predict --csv data/raw/Food_Delivery_Times.csv --output predictions.csv
```
**Tests:**
```bash
python -m pytest -q
```
**API** (details in app/README.md):
```bash
uvicorn app.model_results:app --reload
```
Then open http://127.0.0.1:8000/docs.

The trained models are already in model_pipeline/artifacts/, so the API and the predictions work without training again.

## Results
Ridge is the main model. 80/20 split with seed 42 (800 train / 200 test), 5-fold cross-validation on the training set.

| Model | CV RMSE (mean ± std) | Test RMSE | Test MAE | Test R² |
|---|---|---|---|---|
| Ridge | 10.976 ± 0.694 | 8.762 | 5.931 | 0.829 |
| CatBoost (benchmark) | 11.470 ± 1.027 | 9.209 | 6.268 | 0.811 |
| Baseline (mean) | 22.290 ± 0.795 | - | - | - |

The test set has only 200 rows, so I trust the CV figure more. Ridge and ElasticNet are tied within the noise, and I chose Ridge because it is simpler and easier to explain.

## Key decisions
- Missing values are imputed inside the pipeline (a "Missing" category for the categorical features, the median for the numeric ones), fitted on the training folds only. I did not drop rows because it removes 2 of the 6 slowest deliveries.
- A regularized linear model was my main model, and CatBoost is the benchmark. CatBoost did not beat Ridge on this data (it is not tuned).
- The model error grows with the distance (MAE 3.9 min up to 5 km, 8.6 min from 15 to 20 km).

## Reports
- reports/EDA_report.md: key patterns, outliers and assumptions.
- reports/model_notes.md: modeling logic, metric choice and tuning approach.
- reports/explainability.md: what drives the predictions.
- reports/error_insights.md: when and why the model fails.
- strategic_reflections.md: strategic questions, including the disclosure of the GenAI use.

## Notes
- The SQL queries in sql/sql_queries.sql were not executed on an Impala cluster.
- I used Claude (Anthropic) during the project. What I used it for and how I validated the output is in strategic_reflections.md (question 3).
- I worked on Linux (Ubuntu) with Python 3.14.4, so the commands may differ on other operating systems. For example, on Windows the virtual environment is activated with **.venv\Scripts\activate** instead of **source .venv/bin/activate.**