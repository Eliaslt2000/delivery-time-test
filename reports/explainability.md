# Explainability

Three tools, computed in notebooks/model_training.ipynb (sections 4 and 7):

- **Ridge coefficients.** The change in the predicted time when a feature goes up by one unit with the others fixed. The numeric features are standardized, so I divide by the std of each feature to get minutes per unit.
- **Permutation importance** (test set, Ridge and CatBoost). How much the RMSE increases, in minutes, when one feature is shuffled. A feature that matters hurts the model when it is shuffled.
- **SHAP** (CatBoost). The mean absolute contribution of each feature to the prediction, in minutes.

## Which features matter most

| Feature | Ridge permutation (min) | CatBoost permutation (min) | CatBoost mean \|SHAP\| (min) |
|---|---|---|---|
| Distance_km | 16.26 | 16.00 | 14.52 |
| Preparation_Time_min | 4.02 | 4.09 | 6.16 |
| Traffic_Level | 2.18 | 1.78 | 2.35 |
| Weather | 1.32 | 0.97 | 2.21 |
| Courier_Experience_yrs | 0.36 | 0.34 | 1.49 |
| Time_of_Day | 0.13 | 0.13 | 0.68 |
| Vehicle_Type | 0.03 | -0.01 | 0.27 |

- Distance matters most by far. Then preparation time, then traffic and weather. Both models and the three tools agree on the order.
- This matches the EDA (distance, then preparation time, then traffic and weather).
- Experience, time of day and vehicle type are close to zero in the permutation importance. SHAP gives them a bit more weight than the permutation test, but they are still small.

## What the Ridge coefficients say

Numeric features (the coefficient is per 1 std; dividing by the std gives minutes per unit):

| Feature | Coefficient (per std) | Std | Minutes per unit |
|---|---|---|---|
| Distance_km | 16.97 | 5.72 | **2.96 min per extra km** |
| Preparation_Time_min | 6.95 | 7.22 | **0.96 min per extra minute** |
| Courier_Experience_yrs | -1.86 | 2.90 | -0.64 min per extra year |

So each extra km adds about 3 minutes, and each extra minute of preparation adds about 1 minute to the delivery time.

Categorical features (minutes added or removed against the model baseline; compare categories inside the same feature):

- **Traffic:** High +4.97, Medium -0.38, Low -5.73. High traffic adds about 10.7 min compared with Low.
- **Weather:** Snowy +4.46, Foggy +1.54, Rainy +0.56, Windy -2.61, Clear -4.32. Snowy is about 8.8 min slower than Clear.
- **Time of day:** Evening -0.02, Afternoon -0.98, Morning -1.86, Night -1.99. The "Missing" category is +4.83, but it is a small group of rows and the whole feature has almost no importance, so I do not trust it as a real effect.
- **Vehicle type:** Scooter -0.68, Car +0.61, Bike +0.07: close to zero.

## What happens with experience, time of day and vehicle type
They add almost nothing. Shuffling experience moves the RMSE by 0.36 min, time of day by 0.13 and vehicle type by 0.03, so the model barely needs them.

## Limitations
- Permutation importance comes from the 200 test rows, so values below about 0.3 min cannot be told apart from zero (see the std in the notebook).
- The coefficients of different categories are only comparable inside the same feature.
- Importance is not causality: the model describes the data, and it does not prove that changing a feature changes the delivery time.
