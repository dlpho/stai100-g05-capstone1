# Weather Variables and Rice Yield

## Rainfall / Precipitation and Yield

The relationship between rainfall and rice yield is highly dependent on seasonal timing and ecosystem type. Koide et al. (2013) found strong positive lag correlations (r = 0.7 to 0.8, p < 0.01) between national rice production and seasonal rainfall from October to December of the previous year, which serves as a critical period for dry-season planting. Conversely, rainy-season yield displayed significant negative correlations with rainfall during the late harvest months of October to December in the north-central Philippines.

Other studies confirm rainfall as a powerful predictive feature in machine learning contexts, distinct from simple correlation. Cristina (2023) identified average monthly rainfall and total monthly rainfall as highly relevant for capturing yield variability, extracting Principal Component Analysis (PCA) loadings of 0.387 and 0.376, respectively, which indicates their strong weighting as model inputs. Similarly, Coronel et al. (2024) reported that precipitation accounted for 29.75% to 35.57% of feature importance in predictive deep learning models (LSTM/GRU) for Nueva Ecija, indicating its strong utility as a predictive feature for rice yield.

## Temperature and Yield

Temperature dictates metabolic activity, with moderate averages supporting yields but high extremes causing damage. Dorado (2026) identified the optimal temperature range for rice production in Luzon to be between 24°C and 34°C. Minimum (nighttime) temperatures present a diminishing positive relationship in regression modeling. Relative to an omitted baseline category of extremely cool nights (6°C–12°C), Dorado (2026) demonstrated that an additional day with a minimum temperature ≥ 24°C increases harvests by a coefficient of 1.91% (p < 0.05). However, the greatest benefit is seen in the 12°C–18°C bin, which increases harvest by a coefficient of 2.97% relative to the baseline. This indicates that while warmer nights are better than extreme cold, the positive impact progressively diminishes as nighttime temperatures rise from the optimal 12°C–18°C range into the ≥ 24°C range.

The overall influence of temperature on predictive modeling is substantial. Coronel et al. (2024) found that temperature was the single most influential predictive feature for rice yield in Nueva Ecija, capturing between 46.54% and 48.44% of the predictive importance in neural network models. While Stuecker et al. (2018) noted that temperature currently exhibits a much lower statistical correlation with rice yields compared to soil moisture, they warned that projected future warming beyond current thermal bounds (<28°C) represents a severe threat to tropical rice crop viability.

## Extreme Heat and Yield

When temperatures exceed optimal physiological thresholds, the relationship with yield becomes starkly negative. Lansigan et al. (2000) reported that high temperatures immediately before and during anthesis (flowering) induce spikelet sterility by disturbing pollen shedding and decreasing pollen viability. Specifically, shifts in day/night temperatures from 27/22°C to 36/31°C during the reproductive stage drastically reduced kernel quality and total dry weight.

Supporting this physiological mechanism with modern empirical data, Dorado (2026) established that extreme heat has a direct, quantifiable penalty on crop output in regression models. The study found that an additional day in a quarter with an average daily maximum temperature exceeding 34°C is associated with a regression coefficient indicating a 2.16% decrease in regional rice harvest (p < 0.01).

## Extreme Rainfall and Yield

Extreme precipitation acts as a destructive shock to rice crops, particularly when it leads to mechanical damage or flooding. Dorado (2026) quantified this nonlinear damage using fixed-effects panel regression, finding that an additional day in a quarter with an average daily rainfall of at least 54 mm yields a coefficient equating to a 2.29% reduction in rice harvest volume (p < 0.01).

Lansigan et al. (2000) indicated that prolonged periods of heavy rainfall and flooding abort initial crop growth and can lead to significant yield wipeouts when occurring just before harvest. The severity of extreme weather is heavily documented; typhoons, floods, and droughts were responsible for 82.4% of total Philippine rice losses from 1970 to 1990, highlighting that excessive water inputs are fundamentally destructive rather than beneficial.

## Soil Moisture and Yield

Soil moisture serves as an excellent proxy for continuous water availability and correlates positively with rice outcomes when water is scarce. Stuecker et al. (2018) found that soil moisture anomalies in the previous quarter positively correlate with rice production, explaining approximately 10% of the variance at the national level.

This correlation is highly dependent on agricultural infrastructure. Stuecker et al. (2018) observed that soil moisture correlates more strongly with yield in rainfed systems (R = 0.17) than in irrigated systems (R = 0.08), demonstrating that irrigation actively buffers the crop's physiological response to moisture deficits. During the fourth quarter (wet season crop), the correlation between soil moisture and yield breaks down, becoming small or negative because background moisture is already saturated and additional precipitation leads to flood damage.

## Other Relevant Weather Variables

High wind speeds act as destructive agents during maturation and harvest. Koide et al. (2013) found that Accumulated Cyclone Energy (ACE) in October to December exhibited statistically significant negative correlations (p < 0.05) with irrigated yields in specific regions like Central Luzon. In predictive modeling, Coronel et al. (2024) demonstrated that the speed of maximum gust was a highly influential feature, carrying a variable importance score of up to 39.29% in Nueva Ecija algorithms and 27.40% in Pampanga models.

Atmospheric pressure is also a highly informative predictor, often serving as an indicator of incoming tropical depressions. Cristina (2023) identified atmospheric pressure at the station level as a critical input for modeling, returning a high PCA loading of 0.388. Coronel et al. (2024) similarly found that air pressure accounted for 21.50% to 25.68% of variable importance in Pampanga predictive models. Finally, Lansigan et al. (2000) observed that Potential Evapotranspiration (PET) increases significantly during drought conditions like El Niño, directly elevating crop water requirements and inducing water stress.

# Rice Yield / Production and Price

Fluctuations in rice production caused by extreme weather translate directly into market instability. The provided studies establish a mechanism where weather shocks lead to production reductions, which in turn create market supply shocks and price volatility. Jolejole-Foreman & Mallory (2011) established that rice demand is highly inelastic, which makes market prices highly volatile in response to agricultural supply shocks, such as erratic rainfall and drought. Stuecker et al. (2018) additionally noted that severe natural disasters result in evident regional crop shortfalls, which subsequently cause higher volatility in food prices.

When agricultural yields drop, government interventions to manage the deficit can cause localized market impacts. Jolejole-Foreman & Mallory (2011) observed that as the government intervenes by releasing stocks to mitigate these weather-induced supply shocks, farm-to-retail price margins physically diverge. These price margins were shown to significantly increase in major production hubs like Central Luzon, but negatively affected remote regions like Eastern Visayas.

# Cross-Study Patterns and Interpretation

Across the studies, weather-yield relationships are generally nonlinear rather than strictly linear. Temperature and rainfall can support production within favorable ranges, but conditions beyond specific thresholds can become immediately harmful. While water and warmth are necessary for crop growth, crossing specific physiological limits, such as a 34°C maximum temperature or 54 mm of daily rainfall, is associated with negative regression coefficients and reduced harvest.

Furthermore, the timing of these variables modulates their relationship with crop outcomes. The direction of a weather variable's relationship can change depending on the season and crop calendar. For dry-season crops, antecedent rainfall and soil moisture exhibit strong positive correlations because water is the primary limiting factor for planting and growth. Conversely, for wet-season crops, high late-season rainfall and soil moisture show negative correlations because they align chronologically with destructive tropical cyclones, flooding, and saturated soils during the vulnerable harvest stage.

Finally, the strength of these relationships is consistently buffered by existing agricultural infrastructure. Studies demonstrate that rainfed rice systems exhibit stronger correlations with natural weather variables, such as soil moisture and rainfall, than irrigated systems do. Because irrigation actively mitigates the impacts of drought, the positive correlation between rainfall and yield is structurally weakened in those controlled environments, meaning statistical relationships must always be interpreted in the context of the region's farming practices.