"""
WeatherTato — Pydantic Data Models & Schema Definitions
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Union, Literal


# MODULE 2 - STRUCTURED OUTPUTS (PYDANTIC)

class MessageDict(BaseModel):
    """A single message turn from the conversation history."""
    role: str
    content: str


class UserQuery(BaseModel):
    """Request body for the ``POST /api/chat`` endpoint."""
    user_query: str
    history: Optional[List[MessageDict]] = []
    session_id: Optional[str] = None

class LocationEntity(BaseModel):
    """A resolved location entity with geographic coordinates."""
    original_query: str
    resolved_name: str
    granularity: Literal["barangay", "municipality_city", "province"]
    province: str
    region: str
    latitude: float
    longitude: float
    province_latitude: float
    province_longitude: float
    province_id: Optional[int] = None


class TimePeriod(BaseModel):
    """Extracted time period."""
    granularity: Optional[Literal["QUARTER", "YEAR", "MONTH"]] = None
    value: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ExtractedSlots(BaseModel):
    """Extracted slots from the user query."""
    location: Optional[str] = None
    time_period: Optional[TimePeriod] = None
    weather_variables: Optional[List[Literal["RAINFALL", "MEAN_TEMP", "MAX_TEMP", "MIN_TEMP", "WIND_GUST", "SOIL_MOISTURE"]]] = Field(default_factory=list)
    crop_type: Optional[Literal["PALAY"]] = None
    outcome_metric: Optional[Literal["YIELD", "PRODUCTION", "PRICE"]] = None


class TaskExtraction(BaseModel):
    """Task and slot extraction structured output."""
    action: Literal["GET_WEATHER_DATA", "GET_CROP_DATA", "ANALYZE_CORRELATION", "PREDICT_OUTCOME", "DESCRIBE_CAPABILITIES", "UNKNOWN"]
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    slots: ExtractedSlots


class AgentState(BaseModel):
    """LangGraph state object shared across all 5 pipeline nodes."""
    user_query: str
    intent: Optional[str] = None
    topic: Optional[str] = None
    location: Optional[LocationEntity] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    daily_vars: Optional[List[str]] = None
    granularity: Optional[str] = None
    inner_aggregation: Optional[str] = None
    find_extreme: Optional[str] = None
    weather_data_markdown: Optional[str] = None
    final_response: Optional[str] = None
    error: Optional[str] = None
    waiting_for_location: bool = False
    messages: Optional[List[Any]] = Field(default_factory=list)
    tool_calls: Optional[List[Any]] = Field(default_factory=list)
    summary: Optional[str] = ""
    tool_iteration_count: int = 0

    # Task + Slot Extraction Fields
    active_action: Optional[str] = None
    slots: Optional[dict] = Field(default_factory=dict)
    missing_slots: Optional[List[str]] = Field(default_factory=list)
    is_ready_for_tools: bool = False
