# Model notes

## Goal
Predict `Delivery_Time_min` (minutes) from distance, preparation time, courier experience, weather, traffic, time of day and vehicle type. `Order_ID` is not used.

## Data and split
- 1000 rows. Random 80/20 split with seed 42: 800 for training and 200 for the test set.
- The test set is used once, at the end. All the comparisons use 5-fold cross-validation on the training set only.

## Preprocessing
It is inside the pipeline, so it is fitted on the training folds only (no leakage), and it is saved with the model, so the API applies exactly the same steps.

- Numeric features: median imputation and standardization.
- Categorical features: missing values become a `"Missing"` category, then one-hot encoding (unknown categories are ignored).
- I also tested two other ways to fill the missing categories: the most frequent value and a random draw from the observed values.
- I imputed instead of dropping rows because dropping them removes 2 of the 6 slowest deliveries (see `EDA_report.md`).

## Models
| Model | Why |
|---|---|
| `baseline_mean` | Always predicts the training mean. It is the floor that any model must beat. |
| Ridge (main) | The EDA showed mostly linear and additive relationships, the data is small (800 rows), and the coefficients are easy to read and explain. |
| ElasticNet | A linear model that can set coefficients to zero, to check if some features can be dropped. |
| CatBoost (benchmark) | Gradient boosting. It captures non-linear effects and interactions, so it tells me if a more complex model has something to gain. |

## Metric choice
- **RMSE** is the main metric to compare models: it is in minutes and it punishes big misses, which are the expensive ones for the business.
- **MAE** is the typical miss in minutes, easy to explain to the operations team.
- **R²** is the share of the variation that the model explains, and it shows the distance to the baseline (R² of about 0).
- I also use the **std across folds** to know if a gap between models is bigger than the noise.

## Tuning approach
- **Ridge:** `RidgeCV` tries 13 values of alpha from 0.001 to 1000 with internal cross-validation. The chosen alpha is 10.
- **ElasticNet:** `ElasticNetCV` with `l1_ratio` in 0.1, 0.5, 0.9 and 1.0 and 5-fold CV, with its own alpha path.
- **CatBoost:** fixed, cautious values (500 iterations, learning rate 0.05, depth 4, `l2_leaf_reg` 5). I did **not** tune it, so its result is a benchmark and it could improve a little.
- The test set was never used to choose anything.

## Results

### Cross-validation (5 folds, training set)
| Model | RMSE (mean ± std) | MAE (mean) | R² (mean) |
|---|---|---|---|
| ElasticNet (Missing) | 10.975 ± 0.687 | 6.770 | 0.753 |
| Ridge (Missing) | 10.976 ± 0.694 | 6.792 | 0.753 |
| Ridge (most frequent) | 11.052 ± 0.670 | 6.835 | 0.750 |
| Ridge (random) | 11.098 ± 0.694 | 6.860 | 0.748 |
| CatBoost | 11.470 ± 1.027 | 7.156 | 0.730 |
| Baseline (mean) | 22.290 ± 0.795 | 17.920 | -0.010 |

### Test set (200 rows, used once)
| Model | RMSE | MAE | R² |
|---|---|---|---|
| Ridge | 8.762 | 5.931 | 0.829 |
| CatBoost | 9.209 | 6.268 | 0.811 |

## Decision
Ridge with the `"Missing"` category.

- ElasticNet has the lowest RMSE, but the gap with Ridge is 0.0016 min (about 0.1 second), far smaller than the std (about 0.69): it is a tie.
- The imputation choices differ by 0.08 and 0.12 min, also inside the noise. I keep `"Missing"` because it is the simplest to explain and maintain.
- CatBoost is 0.49 min worse than Ridge in CV, which is also within the fold-to-fold spread (0.69 and 1.03), and it is less stable. It does not beat the simpler model on this data.
- All the linear options cut the baseline error roughly in half (RMSE 22.29 to about 10.98).
- So I choose Ridge for other reasons: it is simpler, its coefficients are easy to explain, and it is more stable between folds.

## Limitations
- The test set has only 200 rows, so it is noisy. The test RMSE (8.76) is better than the CV RMSE (10.98), but I do not read that as an improvement: the CV estimate is the more reliable one.
- CatBoost was not tuned.
- The shapes of the features (see `EDA_report.md`) suggest that the dataset is synthetic, so real delivery data may behave differently.
- The model has only seen distances from 0.5 to 20 km and preparation times from 5 to 29 min. Outside that range it extrapolates, and the API warns about it.
