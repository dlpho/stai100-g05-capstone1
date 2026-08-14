"""
WeatherTato — Open-Meteo Weather Data Service
"""
import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)


# ---------------------------------------------------------------------------
# Monthly aggregation config (WeatherTato monthly weather feature set)
# ---------------------------------------------------------------------------
# How each daily Open-Meteo variable collapses to a monthly value.
MONTHLY_AGG = {
    "precipitation_sum": "sum",               # monthly total rainfall (mm)
    "temperature_2m_mean": "mean",            # avg of daily mean temp (C)
    "temperature_2m_max": "mean",             # avg of daily max temp (C)
    "temperature_2m_min": "mean",             # avg of daily min temp (C)
    "surface_pressure_mean": "mean",          # avg surface pressure (hPa)
    "soil_moisture_0_to_100cm_mean": "mean",  # avg soil moisture
}

# Dorado-study thresholds for the derived extreme-day counts.
EXTREME_RAIN_THRESHOLD_MM = 54.0   # a day is "extreme rainfall" if precip >= this
EXTREME_HEAT_THRESHOLD_C = 34.0    # a day is "extreme heat" if daily max temp >= this

DEFAULT_WEATHER_VARS = list(MONTHLY_AGG.keys())


def fetch_monthly_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    daily_vars: list | None = None,
) -> pd.DataFrame:
    """Fetch daily Open-Meteo Archive data and collapse it to monthly rows.

    Each daily variable is aggregated per MONTHLY_AGG (precipitation summed,
    all other variables averaged). Two derived counts are also
    computed from the daily series (Dorado study):
      - extreme_rain_days: days where precipitation_sum >= 54 mm
      - extreme_heat_days: days where temperature_2m_max >= 34 C

    Returns a DataFrame with columns:
        year, month, <each requested variable>, extreme_rain_days, extreme_heat_days
    """
    daily_vars = list(daily_vars) if daily_vars else DEFAULT_WEATHER_VARS

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": daily_vars,
        "timezone": "Asia/Manila",
    }

    responses = openmeteo.weather_api(url, params=params, timeout=120)
    response = responses[0]
    daily = response.Daily()

    daily_data = {
        "date": pd.date_range(
            start=pd.to_datetime(daily.Time(), unit="s", utc=True),
            end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=daily.Interval()),
            inclusive="left",
        ).tz_convert("Asia/Manila")
    }
    for i, var in enumerate(daily_vars):
        daily_data[var] = daily.Variables(i).ValuesAsNumpy()

    df = pd.DataFrame(daily_data).set_index("date")

    # Derived extreme-day flags (0/1 per day), computed before grouping.
    if "precipitation_sum" in df:
        df["extreme_rain_days"] = (df["precipitation_sum"] >= EXTREME_RAIN_THRESHOLD_MM).astype(int)
    if "temperature_2m_max" in df:
        df["extreme_heat_days"] = (df["temperature_2m_max"] >= EXTREME_HEAT_THRESHOLD_C).astype(int)

    df["year"] = df.index.year
    df["month"] = df.index.month

    agg_spec = {var: MONTHLY_AGG.get(var, "mean") for var in daily_vars}
    if "extreme_rain_days" in df:
        agg_spec["extreme_rain_days"] = "sum"
    if "extreme_heat_days" in df:
        agg_spec["extreme_heat_days"] = "sum"

    monthly = df.groupby(["year", "month"]).agg(agg_spec).reset_index()

    var_cols = [v for v in daily_vars if v in monthly.columns]
    derived_cols = [c for c in ("extreme_rain_days", "extreme_heat_days") if c in monthly.columns]
    return monthly[["year", "month"] + var_cols + derived_cols]


def get_weather_analytics(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    daily_vars: list,
    granularity: str = "day",
    inner_aggregation: str = "mean",
    find_extreme: str = "none"
) -> str:
    """Fetch and aggregate historical weather data from the Open-Meteo Archive API."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": daily_vars,
        "timezone": "Asia/Manila"
    }
    
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    
    md_output = f"### Historical Weather Data (Analytics) for {lat}, {lon}\n\n"
    
    if daily_vars and response.Daily():
        daily = response.Daily()
        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        ).tz_convert("Asia/Manila")}
        
        for i, var in enumerate(daily_vars):
            daily_data[var] = daily.Variables(i).ValuesAsNumpy()
            
        df = pd.DataFrame(data=daily_data)
        
        # 1. Map Time Buckets
        freq_map = {"day": "D", "month": "ME", "year": "YE"}
        freq = freq_map.get(granularity, "D")
        grouped = df.set_index("date").groupby(pd.Grouper(freq=freq))
        
        # 2. Apply Intraday Math Equations
        agg_funcs = {"mean": "mean", "max": "max", "min": "min"}
        agg_func = agg_funcs.get(inner_aggregation, "mean")
        processed_df = getattr(grouped, agg_func)()
        
        # 3. Apply Conditional Extreme Filtering Logic
        if find_extreme == "highest":
            # Find row with max value for the first variable
            target_var = daily_vars[0]
            target_idx = processed_df[target_var].idxmax()
            processed_df = processed_df.loc[[target_idx]]
            md_output += f"**Isolated Highest Period ({target_var})**\n\n"
        elif find_extreme == "lowest":
            target_var = daily_vars[0]
            target_idx = processed_df[target_var].idxmin()
            processed_df = processed_df.loc[[target_idx]]
            md_output += f"**Isolated Lowest Period ({target_var})**\n\n"
            
        # Reset index so date is a column again
        processed_df = processed_df.reset_index()
        
        md_output += f"#### Aggregated Data ({granularity} / {inner_aggregation})\n" + processed_df.to_markdown(index=False) + "\n\n"
        
    return md_output


def get_weather_forecast(lat: float, lon: float, daily_vars: list) -> str:
    """Fetch a 14-day weather forecast from the Open-Meteo Forecast API."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": daily_vars,
        "timezone": "Asia/Manila",
        "forecast_days": 14
    }
    
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    
    md_output = f"### Weather Forecast for {lat}, {lon}\n\n"
    
    if daily_vars and response.Daily():
        daily = response.Daily()
        daily_data = {"date": pd.date_range(
            start = pd.to_datetime(daily.Time(), unit = "s", utc = True),
            end = pd.to_datetime(daily.TimeEnd(), unit = "s", utc = True),
            freq = pd.Timedelta(seconds = daily.Interval()),
            inclusive = "left"
        ).tz_convert("Asia/Manila")}
        
        for i, var in enumerate(daily_vars):
            daily_data[var] = daily.Variables(i).ValuesAsNumpy()
            
        daily_df = pd.DataFrame(data=daily_data)
        md_output += "#### Daily Forecast\n" + daily_df.to_markdown(index=False) + "\n\n"
        
        # Pre-compute exact aggregates to prevent LLM math hallucinations
        if not daily_df.empty:
            md_output += "#### Summary Statistics (Exact Computations)\n"
            for var in daily_vars:
                if "precipitation" in var or "rain" in var or "duration" in var:
                    md_output += f"- Total {var}: {daily_df[var].sum():.2f}\n"
                if "max" in var:
                    md_output += f"- Absolute Highest {var}: {daily_df[var].max():.2f}\n"
                if "min" in var:
                    md_output += f"- Absolute Lowest {var}: {daily_df[var].min():.2f}\n"
                # Provide averages for temperatures or explicit mean variables
                if "mean" in var or ("temperature" in var and "max" not in var and "min" not in var):
                    md_output += f"- Average {var}: {daily_df[var].mean():.2f}\n"
            md_output += "\n"
        
    return md_output
