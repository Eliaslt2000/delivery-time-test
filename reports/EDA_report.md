# EDA Report

Dataset: Food_Delivery_Times.csv (Kaggle), 1,000 deliveries and 9 columns. The target is Delivery_Time_min. All the analysis is in notebooks/EDA.ipynb.

I worked with three versions of the data:
- **v1**: the raw data, each analysis drops only what it needs.
- **v2**: imputed (median for Courier_Experience_yrs, a "Missing" category for the categorical columns). 1,000 rows.
- **v3**: all the incomplete rows dropped. 883 rows.

---

## 1. Key patterns

**Numeric variables**
- **Distance_km is the main driver.** Correlation 0.78 with the delivery time, about 3 minutes per km. Alone it explains 61% of the variance (R² = 0.61).
- **Preparation_Time_min is the second one.** Correlation 0.31, and each extra preparation minute adds about 0.94 minutes. On top of distance it adds about 10 points of R².
- **Courier_Experience_yrs has almost no effect.** Correlation -0.09.
- The three features are almost uncorrelated with each other (-0.01 to -0.03), so there is no multicollinearity.

**Categorical variables**
- **Traffic_Level:** Low is about 52 min and High about 64 min. After removing the distance effect, it explains about 9% of the remaining variance (η² = 0.09).
- **Weather:** Snowy is the slowest (about 67 min vs about 53 for Clear). After removing distance it explains about 6% (η² = 0.06).
- **Time_of_Day and Vehicle_Type do not show a meaningful effect** (p > 0.05 in v1 and v3).
- Traffic and weather are not related to each other (Cramér's V = 0.08, p = 0.12), and none of the categorical pairs are associated (V < 0.09). Each variable gives separate information.

**Overall**
- Traffic and weather are statistically significant (p < 0.001), but their contribution is modest: together about 6 points of R². Preparation time adds more.
- A linear model with all the features reaches R² of about 0.79, so about 21% of the variance stays unexplained.
- The spread of the delivery time grows with the distance, so I expect larger errors in long trips.

**Missing values**
- Weather, Traffic_Level, Time_of_Day and Courier_Experience_yrs have 30 missing values each (3%), but in different rows. 117 rows (11.7%) have at least one.
- v1, v2 and v3 gave the same main conclusions. The only difference is the p-value of Time_of_Day in v2 (0.011), caused by the imputed "Missing" group, whose mean time is higher (about 66 vs 56 min). With 30 rows it may be chance, and I'll check it with cross-validation.

---

## 2. Outliers

- **Features:** no outliers. The three numeric features have a uniform shape inside their range.
- **Target:** with the IQR rule (fences at -4 and 116 min), there are **6 deliveries above 116 min** (122 to 153 min) and none below.
- All 6 are long trips (14.8 to 19 km), but they are 3.0 to 5.1 standard deviations slower than what a distance-only line predicts, so distance explains only a part of them.
- They are not tied to one category: they appear in three weather types (Clear, Rainy, Windy), in all traffic levels and in all vehicle types.
- Two of them (the slowest, 153 and 141 min) have missing values, so dropping the incomplete rows (v3) leaves only 4 outliers. This is one more reason to impute.
- There are also 3 short trips (under 6 km) with more than 90 minutes. Two of them had foggy weather and high traffic, which can explain part of the delay. I'll review them in the error analysis.
- I kept them. They look like real, slow deliveries and not data errors, and removing them would hide the cases the model should learn to handle. I'll check how much they influence the model, and I'll review them in the error analysis.

---

## 3. Assumptions I made

1. **Order_ID is only an identifier** (unique, no relation with the time), so it is not used as a feature.
2. **Preparation time is known when the prediction is made.** If it were only known after the delivery, using it would leak information. I assume it is an estimate available at order time.
3. **The missing values are mostly random.** The exception is Time_of_Day, whose missing rows seem slower, and I'll test that in cross-validation.
4. **I keep all the rows and impute** inside the modeling pipeline, fitted on the training folds only. The dataset is small, and dropping 11.7% of it increases the risk of overfitting.
5. **The relation with distance is roughly linear.** The scatter plots support it, and a linear model is the main model.
6. **The effect of each category is read after removing distance** (ANOVA on the residual), so a longer route does not look like a category effect.
7. **The R² and η² of the EDA are in-sample.** They describe the data, they don't measure how the model will perform. The real numbers will come from cross-validation.
8. **I use 0.05 as the significance line.** For η², I use the usual guide: about 0.01 small, 0.06 medium, 0.14 or more large.


---

## 4. Decisions for the modeling

- I'll use a regularized linear regression as the main model (with scaling and one-hot encoding), and CatBoost as the benchmark.
- I'll use cross-validation and not a single split, because the dataset is small and one split would be too noisy.
- I'll compare the imputation options in CV (median with a "Missing" category, and a random sample), so the choice is based on the error and not on my guess.
