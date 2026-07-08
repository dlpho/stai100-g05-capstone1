from datetime import datetime
import pandas as pd
from typing import Dict, Any
from tools.weather_api import fetch_forecast_data, fetch_historical_data
from core.prompts import CLASSIFY_PROMPT, DATE_EXTRACTION_PROMPT

def df_to_markdown(df: pd.DataFrame) -> str:
    """
    Convert a Pandas DataFrame into a standard Markdown table without external dependencies.
    """
    cols = df.columns.tolist()
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"
    rows = []
    for _, row in df.iterrows():
        rows.append("| " + " | ".join(str(val) for val in row) + " |")
    return "\n".join([header, separator] + rows)

class WeatherRAGHandler:
    def __init__(self, llm):
        self.llm = llm

    def classify_intent(self, question: str) -> str:
        """
        Classifies the user question into one of the RAG categories.
        """
        prompt = CLASSIFY_PROMPT.format(question=question)
        try:
            response = self.llm.invoke(prompt)
            result = response.content if hasattr(response, "content") else str(response)
            result = result.strip()
            
            # Clean possible markdown or prose surrounding the output
            for category in [
                "HISTORICAL_PRECIPITATION",
                "HISTORICAL_TEMPERATURE",
                "HISTORICAL_GENERAL_SUMMARY",
                "FORECAST_IRRIGATION",
                "FORECAST_CROP_ALERT",
                "FORECAST_FIELD_WORK",
                "GENERAL",
                "BOT_INFO"
            ]:
                if category in result:
                    return category
        except Exception as e:
            # Fallback to general forecast in case of error
            pass
        return "GENERAL"

    def extract_date_range(self, question: str) -> tuple[str, str]:
        import datetime
        import json
        import re
        
        today_dt = datetime.date.today()
        today_str = today_dt.strftime("%Y-%m-%d")
        weekday_str = today_dt.strftime("%A")
        
        prompt = DATE_EXTRACTION_PROMPT.format(
            today=today_str,
            weekday=weekday_str,
            question=question
        )
        
        # Fallback defaults (past 365 days)
        yesterday_dt = today_dt - datetime.timedelta(days=1)
        default_start = (yesterday_dt - datetime.timedelta(days=365)).strftime("%Y-%m-%d")
        default_end = yesterday_dt.strftime("%Y-%m-%d")
        
        try:
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, "content") else str(response)
            response_text = response_text.strip()
            
            # Extract JSON from markdown code blocks or prose
            md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
            if md_match:
                json_str = md_match.group(1).strip()
            else:
                start = response_text.find('{')
                end = response_text.rfind('}')
                if start != -1 and end != -1:
                    json_str = response_text[start:end+1]
                else:
                    json_str = response_text
            
            data = json.loads(json_str)
            start_date = data.get("start_date") or default_start
            end_date = data.get("end_date") or default_end
            
            # Validate ISO format
            datetime.date.fromisoformat(start_date)
            datetime.date.fromisoformat(end_date)
            
            # Cap at yesterday for historical archive
            yesterday_str = yesterday_dt.strftime("%Y-%m-%d")
            if start_date > yesterday_str:
                start_date = yesterday_str
            if end_date > yesterday_str:
                end_date = yesterday_str
            if start_date > end_date:
                start_date, end_date = end_date, start_date
                
            return start_date, end_date
            
        except Exception:
            return default_start, default_end

    def retrieve_and_aggregate(self, question: str, latitude: float, longitude: float, category: str | None = None) -> str:
        """
        Main RAG entry point: detects category, retrieves raw API data, aggregates using Pandas, and formats.
        """
        if category is None:
            category = self.classify_intent(question)
        
        # Branch based on whether historical or forecast category is requested
        if category.startswith("HISTORICAL"):
            # Extract start and end dates from LLM date parsing slots
            start_date_str, end_date_str = self.extract_date_range(question)
            
            try:
                raw_data = fetch_historical_data(latitude, longitude, start_date_str, end_date_str)
                return self._aggregate_historical(raw_data, category)
            except Exception as e:
                return f"Error retrieving historical data: {str(e)}"
        else:
            try:
                raw_data = fetch_forecast_data(latitude, longitude)
                return self._aggregate_forecast(raw_data, category)
            except Exception as e:
                return f"Error retrieving forecast data: {str(e)}"

    def _aggregate_historical(self, raw_data: Dict[str, Any], category: str) -> str:
        if "daily" not in raw_data:
            return "No historical daily data available."
            
        daily = raw_data["daily"]
        df = pd.DataFrame({
            "Date": daily["time"],
            "Max_Temp": daily.get("temperature_2m_max", []),
            "Min_Temp": daily.get("temperature_2m_min", []),
            "Precipitation": daily.get("precipitation_sum", []),
            "Rain": daily.get("rain_sum", [])
        })
        
        df["Date"] = pd.to_datetime(df["Date"])
        df["Month"] = df["Date"].dt.strftime("%Y-%m")
        
        if category == "HISTORICAL_PRECIPITATION":
            # Group daily rain sums by month
            agg = df.groupby("Month").agg(
                Total_Rainfall_mm=("Rain", "sum"),
                Rainy_Days_Count=("Rain", lambda x: (x > 0.1).sum())
            ).reset_index()
            
            # Characterize rainfall amount (wet/dry thresholds)
            def characterize_rainfall(row):
                total = row["Total_Rainfall_mm"]
                if total > 150:
                    return "Wet Month (High Rainfall)"
                elif total < 50:
                    return "Dry Month (Low Rainfall)"
                return "Normal Month"
                
            agg["Characterization"] = agg.apply(characterize_rainfall, axis=1)
            agg = agg.round(1)
            agg.columns = ["Month", "Total Rainfall (mm)", "Rainy Days (Days)", "Characterization"]
            
            table_md = df_to_markdown(agg)
            return (
                "### Observed Historical Precipitation Summary (Past 12 Months)\n\n"
                f"{table_md}\n\n"
                "*(Note: Rainfall characterization based on 150mm wet / 50mm dry thresholds)*"
            )
            
        elif category == "HISTORICAL_TEMPERATURE":
            # Summarize average monthly highs/lows
            agg = df.groupby("Month").agg(
                Avg_Max_Temp=("Max_Temp", "mean"),
                Avg_Min_Temp=("Min_Temp", "mean")
            ).reset_index()
            agg = agg.round(1)
            agg.columns = ["Month", "Average High (°C)", "Average Low (°C)"]
            
            table_md = df_to_markdown(agg)
            return (
                "### Observed Historical Temperature Profile (Past 12 Months)\n\n"
                f"{table_md}"
            )
            
        else: # HISTORICAL_GENERAL_SUMMARY
            agg = df.groupby("Month").agg(
                Avg_Max_Temp=("Max_Temp", "mean"),
                Avg_Min_Temp=("Min_Temp", "mean"),
                Total_Precipitation=("Precipitation", "sum")
            ).reset_index()
            agg = agg.round(1)
            agg.columns = ["Month", "Avg Max Temp (°C)", "Avg Min Temp (°C)", "Total Rain (mm)"]
            
            table_md = df_to_markdown(agg)
            return (
                "### Annual Observed Historical Weather Summary\n\n"
                f"{table_md}"
            )

    def _aggregate_forecast(self, raw_data: Dict[str, Any], category: str) -> str:
        if "daily" not in raw_data:
            return "No forecast data available."
            
        # Extract daily fields (all variables including native mean humidity)
        daily = raw_data["daily"]
        df_forecast = pd.DataFrame({
            "Date": daily["time"],
            "Max_Temp": daily.get("temperature_2m_max", []),
            "Min_Temp": daily.get("temperature_2m_min", []),
            "Rain_Sum": daily.get("rain_sum", []),
            "Showers_Sum": daily.get("showers_sum", []),
            "Precip_Sum": daily.get("precipitation_sum", []),
            "Max_Wind": daily.get("wind_speed_10m_max", []),
            "Max_Humidity": daily.get("relative_humidity_2m_max", [])
        })
        df_forecast = df_forecast.round(1)
        
        if category == "FORECAST_IRRIGATION":
            # Upcoming rain sums
            df_irr = df_forecast[["Date", "Rain_Sum", "Showers_Sum", "Precip_Sum"]].copy()
            df_irr.columns = ["Date", "Rain (mm)", "Showers (mm)", "Total Forecast Precipitation (mm)"]
            table_md = df_to_markdown(df_irr)
            return (
                "### Forecast Rainfall Summary (Next 14 Days)\n\n"
                f"{table_md}"
            )
            
        elif category == "FORECAST_CROP_ALERT":
            # Temperature and humidity alerts
            df_alert = df_forecast[["Date", "Max_Temp", "Min_Temp", "Max_Humidity"]].copy()
            df_alert.columns = ["Date", "Max Temp (°C)", "Min Temp (°C)", "Max Humidity (%)"]
            
            def get_crop_alerts(row):
                alerts = []
                max_t = row["Max Temp (°C)"]
                min_t = row["Min Temp (°C)"]
                max_h = row["Max Humidity (%)"]
                
                if max_t > 35:
                    alerts.append("High Temperature Stress Risk (>35°C)")
                if min_t < 15:
                    alerts.append("Low Temperature Cold Stress Risk (<15°C)")
                if max_h > 85:
                    alerts.append("High Fungal/Pest Risk (Humidity >85%)")
                return ", ".join(alerts) if alerts else "Normal Conditions"
                
            df_alert["Potential Conditions Alert"] = df_alert.apply(get_crop_alerts, axis=1)
            table_md = df_to_markdown(df_alert)
            return (
                "### Crop Conditions & Disease Alert Forecast (Next 14 Days)\n\n"
                f"{table_md}"
            )
            
        elif category == "FORECAST_FIELD_WORK":
            # Dry windows for farming operations
            df_field = df_forecast[["Date", "Precip_Sum", "Max_Wind"]].copy()
            df_field.columns = ["Date", "Precipitation (mm)", "Max Wind (km/h)"]
            
            def evaluate_suitability(row):
                rain = row["Precipitation (mm)"]
                wind = row["Max Wind (km/h)"]
                if rain == 0 and wind < 20:
                    return "Highly Suitable (Dry & Low Wind)"
                elif rain < 2 and wind < 30:
                    return "Moderately Suitable (Damp or Light Wind)"
                else:
                    return "Unsuitable (Heavy Rain or Strong Wind)"
                    
            df_field["Field Suitability"] = df_field.apply(evaluate_suitability, axis=1)
            table_md = df_to_markdown(df_field)
            return (
                "### Farm Field Work Suitability Forecast (Next 14 Days)\n\n"
                f"{table_md}"
            )
            
        else: # GENERAL
            # Standard 14-day weather profile
            df_gen = df_forecast[["Date", "Max_Temp", "Min_Temp", "Precip_Sum", "Max_Wind", "Max_Humidity"]].copy()
            df_gen.columns = ["Date", "Max Temp (°C)", "Min Temp (°C)", "Rain (mm)", "Max Wind (km/h)", "Max Humidity (%)"]
            table_md = df_to_markdown(df_gen)
            return (
                "### Localized Weather Forecast Summary (Next 14 Days)\n\n"
                f"{table_md}"
            )
