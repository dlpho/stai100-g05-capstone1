# WeatherAI Chatbot — Capabilities Reference

This document describes all query types the chatbot can handle, the Open-Meteo API variables it fetches for each, and the data transformations applied before the LLM generates its response.

> **Coverage**: Philippines only. All locations must be resolvable to a barangay, municipality, or province.

---

## Intent Categories

The LLM first classifies every incoming question into one of the intents below. Intent determines which API endpoint is called and which Pandas aggregation is applied.

---

### 1. `BOT_INFO` — Chatbot Identity & Capabilities

**Triggers**: Greetings, help requests, "what can you do?", "who are you?"

- No weather data is fetched.
- The LLM responds directly from the system prompt.
- No location is required.

**Example questions**:
- "Hello! What can you help me with?"
- "What weather questions can I ask?"
- "How do I use this chatbot?"

---

### 2. `GENERAL` — Standard Weather Forecast

**Triggers**: "What's the weather?", "weather this week", "forecast for tomorrow"

**API**: Open-Meteo Forecast (`/v1/forecast`) — **14-day window**

| Open-Meteo Variable | Unit | Column in Table |
|---|---|---|
| `temperature_2m_max` | °C | Max Temp (°C) |
| `temperature_2m_min` | °C | Min Temp (°C) |
| `precipitation_sum` | mm | Rain (mm) |
| `wind_speed_10m_max` | km/h | Max Wind (km/h) |
| `relative_humidity_2m_max` | % | Max Humidity (%) |

**Output**: Daily 14-day weather table.

**Example questions**:
- "What is the weather in Laoag City this week?"
- "Will it be hot tomorrow in Cebu?"
- "Give me the weather forecast for Davao for the next 7 days."

---

### 3. `FORECAST_IRRIGATION` — Rainfall Forecast for Irrigation

**Triggers**: Questions about upcoming rain for watering, water availability, irrigation scheduling.

**API**: Open-Meteo Forecast (`/v1/forecast`) — **14-day window**

| Open-Meteo Variable | Unit | Column in Table |
|---|---|---|
| `rain_sum` | mm | Rain (mm) |
| `showers_sum` | mm | Showers (mm) |
| `precipitation_sum` | mm | Total Forecast Precipitation (mm) |

**Output**: Daily 14-day precipitation breakdown table.

**Example questions**:
- "Will there be enough rain for irrigation in Ilocos Norte next week?"
- "How much rainfall is expected in Batangas over the next 2 weeks?"
- "Is rain coming soon for my crops in Nueva Ecija?"

---

### 4. `FORECAST_CROP_ALERT` — Crop Stress & Disease Risk Forecast

**Triggers**: Questions about heat stress, humidity risk, disease/pest conditions.

**API**: Open-Meteo Forecast (`/v1/forecast`) — **14-day window**

| Open-Meteo Variable | Unit | Column in Table |
|---|---|---|
| `temperature_2m_max` | °C | Max Temp (°C) |
| `temperature_2m_min` | °C | Min Temp (°C) |
| `relative_humidity_2m_max` | % | Max Humidity (%) |

**Alert Thresholds Applied**:

| Condition | Threshold | Alert Label |
|---|---|---|
| High heat stress | Max Temp > 35°C | High Temperature Stress Risk |
| Cold stress | Min Temp < 15°C | Low Temperature Cold Stress Risk |
| Fungal/pest risk | Max Humidity > 85% | High Fungal/Pest Risk |

**Output**: Daily 14-day alert table with a computed `Potential Conditions Alert` column.

**Example questions**:
- "Is there a risk of heat stress for crops in Pampanga next week?"
- "What are the crop alert conditions in Bukidnon?"
- "Will the humidity be high enough to cause disease in my rice fields?"

---

### 5. `FORECAST_FIELD_WORK` — Field Work Suitability Forecast

**Triggers**: Questions about dry windows, suitable days for harvesting, planting, or land preparation.

**API**: Open-Meteo Forecast (`/v1/forecast`) — **14-day window**

| Open-Meteo Variable | Unit | Column in Table |
|---|---|---|
| `precipitation_sum` | mm | Precipitation (mm) |
| `wind_speed_10m_max` | km/h | Max Wind (km/h) |

**Suitability Rules Applied**:

| Condition | Label |
|---|---|
| Rain = 0mm AND Wind < 20 km/h | Highly Suitable (Dry & Low Wind) |
| Rain < 2mm AND Wind < 30 km/h | Moderately Suitable (Damp or Light Wind) |
| Otherwise | Unsuitable (Heavy Rain or Strong Wind) |

**Output**: Daily 14-day suitability table.

**Example questions**:
- "Which days next week are good for harvesting in Isabela?"
- "When can I do land preparation in Cagayan Valley?"
- "Are there dry days coming up for planting in Laguna?"

---

### 6. `HISTORICAL_PRECIPITATION` — Past Rainfall Summary

**Triggers**: Questions about past rainfall, rainy days, historical rain volumes.

**API**: Open-Meteo Archive (`/v1/archive`) — **date range extracted by LLM**

| Open-Meteo Variable | Unit | Used For |
|---|---|---|
| `rain_sum` | mm | Monthly total rainfall & rainy day count |

**Aggregation**: Grouped by month — total rainfall (mm) and count of rainy days (> 0.1mm threshold).

**Rainfall Characterization**:

| Total Monthly Rainfall | Label |
|---|---|
| > 150 mm | Wet Month (High Rainfall) |
| 50–150 mm | Normal Month |
| < 50 mm | Dry Month (Low Rainfall) |

**Output**: Monthly precipitation summary table for the queried period.

**Example questions**:
- "How much did it rain in Ilocos Norte last year?"
- "What were the rainy months in Leyte in 2023?"
- "Show me rainfall data for Quezon City from January to June 2024."

---

### 7. `HISTORICAL_TEMPERATURE` — Past Temperature Profile

**Triggers**: Questions about past temperatures, historical highs/lows, average temperatures by month.

**API**: Open-Meteo Archive (`/v1/archive`) — **date range extracted by LLM**

| Open-Meteo Variable | Unit | Used For |
|---|---|---|
| `temperature_2m_max` | °C | Monthly average high |
| `temperature_2m_min` | °C | Monthly average low |

**Aggregation**: Grouped by month — mean of daily max and min temperatures.

**Output**: Monthly temperature profile table for the queried period.

**Example questions**:
- "What were the average temperatures in Baguio last year?"
- "How hot was it in Cebu in the summer of 2023?"
- "What is the historical temperature range in Davao from 2022 to 2023?"

---

### 8. `HISTORICAL_GENERAL_SUMMARY` — Full Historical Climate Overview

**Triggers**: General historical climate questions, annual summaries, overall past weather overview.

**API**: Open-Meteo Archive (`/v1/archive`) — **date range extracted by LLM**

| Open-Meteo Variable | Unit | Used For |
|---|---|---|
| `temperature_2m_max` | °C | Monthly average high |
| `temperature_2m_min` | °C | Monthly average low |
| `precipitation_sum` | mm | Monthly total precipitation |

**Aggregation**: Grouped by month — average temperatures and total rainfall combined.

**Output**: Combined monthly climate summary table.

**Example questions**:
- "Give me a historical weather overview for Iloilo in 2023."
- "What was the climate like in Zamboanga last year?"
- "Summarize the weather in Metro Manila from 2022 to 2023."

---

## Out-of-Scope Queries

The chatbot will refuse or redirect the following:

| Type | Response |
|---|---|
| Farming/planting/crop advice | Refused — not a farming advisor |
| Non-weather topics | Refused — weather-only scope |
| Locations outside the Philippines | No match in location database |
| PII in questions (email, phone, credit card) | Stripped before processing |
| Prompt injection attempts | Blocked |

---

## Date Resolution

For all historical intents, the LLM extracts a `start_date` and `end_date` from the natural language question:

- Specific year → `YYYY-01-01` to `YYYY-12-31`
- Specific month → exact month boundaries
- Relative ("last month", "last year") → resolved against today's date
- Future dates → capped at yesterday (archive data has a ~5-day lag)
- Default fallback → past 365 days ending yesterday

---

## 🚦 Decision Thresholds & Classification Rules

All thresholds are applied in `app/core/rag_handler.py` during Pandas aggregation, before the LLM sees the data. The LLM receives the pre-labelled table and interprets it — it does **not** apply thresholds itself.

---

### Crop Stress & Disease Alert Thresholds

> Applied to: `FORECAST_CROP_ALERT` intent  
> Variable source: Open-Meteo Forecast daily fields  
> Output column: `Potential Conditions Alert`

| Metric | Variable | Threshold | Alert Generated |
|---|---|---|---|
| Heat stress | `temperature_2m_max` | > 35 °C | High Temperature Stress Risk (>35°C) |
| Cold stress | `temperature_2m_min` | < 15 °C | Low Temperature Cold Stress Risk (<15°C) |
| Fungal / pest risk | `relative_humidity_2m_max` | > 85 % | High Fungal/Pest Risk (Humidity >85%) |
| No alert | — | None of the above trigger | Normal Conditions |

> Multiple alerts can appear on the same day (comma-separated). If none trigger, the cell shows **Normal Conditions**.

---

### Field Work Suitability Rules

> Applied to: `FORECAST_FIELD_WORK` intent  
> Variable source: Open-Meteo Forecast daily fields  
> Output column: `Field Suitability`

Rules are evaluated in priority order — the first matching rule wins:

| Priority | Rain Condition | Wind Condition | Suitability Label |
|---|---|---|---|
| 1 (Best) | `precipitation_sum` = 0 mm | `wind_speed_10m_max` < 20 km/h | Highly Suitable (Dry & Low Wind) |
| 2 | `precipitation_sum` < 2 mm | `wind_speed_10m_max` < 30 km/h | Moderately Suitable (Damp or Light Wind) |
| 3 (Worst) | Otherwise | Otherwise | Unsuitable (Heavy Rain or Strong Wind) |

---

### Rainfall Characterization (Historical)

> Applied to: `HISTORICAL_PRECIPITATION` intent  
> Variable source: Open-Meteo Archive `rain_sum`, aggregated to monthly totals  
> Output column: `Characterization`  
> Rainy day threshold: a day counts as rainy if `rain_sum` > **0.1 mm**

| Monthly Rainfall Total | Characterization Label |
|---|---|
| > 150 mm | Wet Month (High Rainfall) |
| 50 – 150 mm | Normal Month |
| < 50 mm | Dry Month (Low Rainfall) |
