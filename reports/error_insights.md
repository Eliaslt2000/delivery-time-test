# Error insights

All the numbers come from the 200 test rows and the Ridge model (notebooks/model_training.ipynb, sections 5 and 7).

**Residual = real time - predicted time.** A positive residual means the model **underestimates** (it says less time than the real one, so the customer waits longer than promised). A negative residual means it overestimates.

## Global picture
- RMSE 8.762, MAE 5.931, bias -0.78 min.
- On average the model slightly overestimates: 37.5% of the deliveries are underestimated and 62.5% overestimated.
- 34 of 200 deliveries (17%) have an error over 10 min: 14 are underestimated and 20 overestimated.

## When does the model fail most?

**Distance (the clearest pattern).** The longer the trip, the larger the error.

| Distance band | n | Bias (min) | MAE (min) |
|---|---|---|---|
| 0-5 km | 51 | -0.08 | 3.86 |
| 5-10 km | 50 | -0.92 | 4.59 |
| 10-15 km | 47 | -2.31 | 6.66 |
| 15-20 km | 52 | +0.05 | 8.59 |

The residual plot has a funnel shape: the errors are tight for short predicted times and spread out for long ones, so the model is less certain on long deliveries.

**Weather, traffic and time of day.**

| Group | n | Bias | MAE | Share underestimated |
|---|---|---|---|---|
| Foggy | 21 | +5.82 | 9.76 | 0.67 |
| Rainy | 40 | -1.21 | 6.40 | 0.38 |
| Windy | 16 | +1.12 | 6.13 | 0.44 |
| Snowy | 20 | -0.85 | 6.10 | 0.40 |
| Clear | 95 | -2.27 | 4.83 | 0.31 |
| Traffic High | 38 | +2.83 | 8.01 | 0.47 |
| Traffic Low | 72 | -2.05 | 6.00 | 0.32 |
| Traffic Medium | 79 | -1.34 | 5.08 | 0.37 |
| Time of day Missing | 6 | -2.08 | 13.72 | 0.17 |

- Foggy and High traffic have the largest errors. Clear weather is the most accurate group.
- Rainy is **not** underestimated (bias -1.21).
- Time of day "Missing" has the largest MAE (13.72), but with only 6 rows I treat it as a clue and not as a conclusion. Night (+4.01, 9 rows) is also a very small group.
- Vehicle type shows small differences (MAE from 4.82 for Car to 6.16 for Bike).

## Is the fog bias real?
The Foggy group has a bias of +5.82 min, but I checked it before accepting it:
- Three deliveries (+52.6, +34.9 and +30.1 min) explain it. Without them the bias is **0.25**, and the median is only +1.35.
- Out of fold on the 82 foggy rows of the train set, the bias is **+0.45** (median -1.86). The other weather types are also close to zero (from -0.30 to +0.61).
- So the model does not underestimate fog systematically: it is a few extreme deliveries.

## Underestimate or overestimate in the bad cases? Why does it matter?
- The typical case is a slight overestimate, and among the 34 errors over 10 min there are more overestimates (20) than underestimates (14).
- But the **largest** errors are underestimates: the top 5 of the worst-cases table are all positive, and the biggest is +52.6 min (3.0 km, Foggy, High traffic: 90 min real vs 37.4 predicted).
- **Cost of overestimating:** the promised time is longer than needed, so there is lost productivity (for example, a courier could have covered 2 trips instead of 1) and a worse plan for the operation.
- **Cost of underestimating:** late deliveries and unhappy customers. It is the more expensive direction, and it is where the biggest misses are.
- Two of the three largest underestimates are short trips with a very long time (3.0 km in 90 min and 5.9 km in 106 min), like the outliers I flagged in the EDA. No feature explains them, so no model could predict them.

## Do the interactions show something a linear model cannot capture?
Yes, there is a hint. In the Weather x Traffic heatmap the cell **Foggy + High traffic** has a mean residual of **+16.5 min**, while the Clear row is negative in all three cells (-1.3, -3.5 and -2.0). A linear model adds the effect of weather and traffic separately, so it cannot capture a combination that is worse than the sum, unless I add an interaction feature. But that cell has very few rows (Foggy has 21 in total), and three of the largest errors are foggy, so I cannot confirm that the effect is real.

## What I would try next (not tested)
- Add an interaction feature (Weather x Traffic_Level) and check it with cross-validation.
- Tune CatBoost with a small search.
- Get more data for fog and high traffic, and review the extreme cases.
- Return a range in the API and not only one number, because the error grows with the distance.

## Limitations
- The test set has 200 rows, so every group-level number (especially with n below 30) is noisy.
- The error is not constant: the typical error of about 6 min in the API is an average, and it is smaller for short trips (3.9 min) and larger for long ones (8.6 min).
