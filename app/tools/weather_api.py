import requests
from typing import Dict, Any

FORECAST_API_URL = "https://api.open-meteo.com/v1/forecast"
HISTORICAL_API_URL = "https://archive-api.open-meteo.com/v1/archive"

def fetch_forecast_data(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Fetch weather forecast data (hourly and daily) for the next 14 days from Open-Meteo.
    
    Args:
        latitude: Latitude coordinate of the location.
        longitude: Longitude coordinate of the location.
        
    Returns:
        A dictionary containing forecast weather data.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,showers_sum,wind_speed_10m_max,relative_humidity_2m_max",
        "timezone": "auto",
        "forecast_days": 14
    }
    
    try:
        response = requests.get(FORECAST_API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Error fetching forecast data: {str(e)}")

def fetch_historical_data(latitude: float, longitude: float, start_date: str, end_date: str) -> Dict[str, Any]:
    """
    Fetch historical weather data for a given date range from Open-Meteo Archive API.
    
    Args:
        latitude: Latitude coordinate of the location.
        longitude: Longitude coordinate of the location.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        
    Returns:
        A dictionary containing historical weather data.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum,relative_humidity_2m_mean",
        "timezone": "auto"
    }
    
    try:
        response = requests.get(HISTORICAL_API_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Error fetching historical data: {str(e)}")
