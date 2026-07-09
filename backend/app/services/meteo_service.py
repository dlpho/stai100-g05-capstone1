import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def get_weather_analytics(lat: float, lon: float, start_date: str, end_date: str, daily_vars: list, granularity: str = "day", inner_aggregation: str = "mean", find_extreme: str = "none") -> str:
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
