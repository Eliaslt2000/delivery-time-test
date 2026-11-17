# Strategic Reflections

## 1. Model Failure: the model underestimates delivery time on rainy days. Do I fix the model, the data or the business expectations?

In my model it is not the rainy days that are underestimated. Rainy has a bias of -1.21 min (a slight overestimate, 40 test rows), so I would not change anything for rain. The underestimation I found is in Foggy (+5.82 min, 21 rows), and it comes from 3 extreme deliveries (see question 4).

If a model did underestimate on rainy days, I would go in this order:

1. **The data first.** How many rainy rows are there, how many are extreme cases, and is the weather label reliable (weather at order time or at delivery time)? If the data or the label is wrong, a better model only learns the same error.
2. **Then the model.** A linear model adds the effect of weather and traffic separately, so I would test an interaction feature (Weather x Traffic_Level) with cross-validation and compare it with CatBoost, which can capture interactions by itself.
3. **Then the business expectation.** Underestimating is the expensive direction (late orders), so in bad weather I would show a wider range or add a safety margin to the promised time while the fix is built.

## 2. Transferability: the model performs well in Mumbai and now it is deployed in São Paulo

I would not assume it transfers. My data has no city column, so the model has never seen a city effect, and São Paulo can differ in traffic patterns, vehicle mix, road network and weather seasons.

1. **Compare the inputs.** Check the distributions of distance, preparation time, traffic, vehicle type and weather in both cities. My API already warns when an input is outside the training range (distance 0.5 to 20 km, preparation 5 to 29 min).
2. **Validate before launch.** Run the model in shadow mode on a local sample and measure MAE and RMSE, and the error by distance band and by weather, as I did in `error_insights.md`. Agree with the business on the error they accept.
3. **Retrain or fine-tune with local data.** With a Ridge model this is cheap and fast, and I can compare it with the Mumbai model using the same cross-validation.
4. **Add city-level features if needed**, for example city, local traffic patterns or holidays.
5. **Monitor after launch.** Track the error by city and trigger a retraining when it goes over the threshold.

## 3. GenAI Disclosure

I used Claude (Anthropic) a lot in this project, as a guide and as a code assistant. This is what I used it for and what I did with the output.

- **Planning and guidance.** Project structure, order of the steps and the git workflow (one branch per part, small commits, pull requests). The file tree is my design. When its files overwrote my empty placeholders (`train.py`, `predict.py`, `preprocessing.py`), I flagged it, and we reorganised the code into my own files (`regression_model.py`, `config.json`).
- **SQL (Part I).** I used it to review my queries (logic and Impala syntax) and to draft `sql_insights.md`. I kept my own structure and assumptions, and I edited and shortened the text. I could not run the queries on Impala, so they were not executed.
- **EDA.** It suggested the checks (correlation heatmap, ANOVA with eta squared, R² by feature set, Cramér's V) and helped with the plotting code. I ran them in my notebook, read the outputs and wrote the conclusions of `EDA_report.md`. Some statements were wrong (mine and the assistant's) and were corrected after checking them in the data, for example the missing values were not all in the same rows, and the outliers were not spread over every group.
- **Modeling pipeline, API and tests.** The code in `model_pipeline/`, `app/model_results.py` and `tests/` was mostly written by Claude. The design decisions were discussed with me: Ridge as the main model, CatBoost as the benchmark, imputation inside the pipeline, no tuning on the test set. I ran everything on my machine (Python 3.14.4), checked that the numbers matched, and ran the 15 tests. I asked for explanations of the metrics, the CatBoost parameters, the plots and the API until I could explain them.
- **Notes and reports.** I wrote my notes in the notebook in my own words, with help for grammar and wording. The first drafts of `model_notes.md`, `explainability.md`, `error_insights.md`, the READMEs and this file were prepared with Claude from my notebook outputs.

**How I validated and modified the output**

- I ran the training and the tests myself and compared the results.
- Every number in the reports has a cell output in my notebook. When I found numbers that were not backed by an output, I rejected them and added cells that print them (the last section of `model_training.ipynb`).
- I checked a suspicious result instead of accepting it: the fog bias (question 4).
- I changed names, structure and wording to mine, and I stated what I could not do: the SQL is not executed and CatBoost is not tuned.

## 4. Your Signature Insight: the model "fails in fog", but it does not

In the test set Foggy has a bias of +5.82 min (21 rows), and the worst errors are mostly foggy. The easy conclusion would be "the model fails in fog, fix the weather feature". I checked it before accepting it:

- **Three deliveries explain it.** Their residuals are +52.6, +34.9 and +30.1 min. Without them the bias is **0.25**, and the median fog residual is only +1.35.
- **A bigger sample says the same.** Out of fold on the 82 foggy rows of the train set, the bias is **+0.45** (median -1.86). The other weather types are also close to zero (from -0.30 to +0.61).
- **Two of the three are short trips with a very long time** (3.0 km in 90 min, 5.9 km in 106 min), the kind of outliers that I flagged in the EDA. No feature explains them.

So fog is not systematically underestimated: it was a few extreme deliveries. My decision was not to change the model or the features for it, and to write the limit in `error_insights.md`. I like it because the table said one thing, a bigger sample said another, and checking it took three cells.

## 5. Going to Production

What is already in the repo is marked as done. The rest is the plan.

1. **Data.** Read the training data from the platform tables (the SQL from Part I is the starting point). Validate the schema, ranges and categories before training, and stop the run if the data does not pass. *(Plan: the API already validates the inputs it receives.)*
2. **Reproducible training.** *(Done.)* One command (`python -m model_pipeline.train`), parameters in `config.json`, fixed seed, pinned `requirements.txt`, and the preprocessing saved inside the model file, so training and serving use exactly the same steps.
3. **Versioning and tracking.** *(Partly done: models and `metrics.json` are saved together.)* Plan: a model registry (for example MLflow) with the model version, the data version, the code commit and the metrics.
4. **Tests.** *(Done: 15 tests for the pipeline and the API.)* Plan: add data-validation tests and a gate that blocks a new model if its CV error is worse than the current one.
5. **Serving.** *(Done: FastAPI with input validation, range warnings, `/health`, `/model-info`, `/predict` and `/predict/batch`.)* Plan: package it in a Docker image, run several workers behind a load balancer, and use a scheduled batch job when real-time is not needed.
6. **CI/CD.** Plan: on every pull request run lint and tests (GitHub Actions); on merge build the image, deploy to staging, then release with shadow mode or a canary and keep the previous model for a quick rollback.
7. **Monitoring.** Plan: (a) input drift (distance, preparation time, traffic and vehicle mix); (b) prediction error when the real delivery time arrives (MAE by distance band, weather and city); (c) latency and error rate of the API; with alerts and a dashboard.
8. **Retraining.** Plan: on a schedule (for example monthly) or when drift or error pass a threshold, always comparing the new model with the current one on the same data before promoting it.
9. **Governance and use.** Plan: a short model card with its limits (the error grows with distance, valid range 0.5 to 20 km, typical error about 6 min), no personal customer data in the features or the logs, and a fallback rule (average by distance band) if the service is down. For the business, show the estimate together with the typical error, because underestimating costs more than overestimating.
