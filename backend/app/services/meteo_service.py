import openmeteo_requests
import requests_cache
import pandas as pd
from retry_requests import retry

# Setup the Open-Meteo API client with cache and retry on error
cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
openmeteo = openmeteo_requests.Client(session=retry_session)

def get_weather_analytics(lat: float, lon: float, start_date: str, end_date: str, daily_vars: list) -> str:
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
            
        daily_df = pd.DataFrame(data=daily_data)
        md_output += "#### Daily Data\n" + daily_df.to_markdown(index=False) + "\n\n"
        
    return md_output

def get_weather_forecast(lat: float, lon: float, daily_vars: list) -> str:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": daily_vars,
        "timezone": "Asia/Manila"
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
        
    return md_output
