"""
WeatherTato — Pydantic Data Models & Schema Definitions
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Union


# MODULE 2 - STRUCTURED OUTPUTS (PYDANTIC)

class MessageDict(BaseModel):
    """A single message turn from the conversation history."""
    role: str
    content: str


class UserQuery(BaseModel):
    """Request body for the ``POST /api/chat`` endpoint."""
    user_query: str
    history: Optional[List[MessageDict]] = []


class LocationEntity(BaseModel):
    """A resolved location entity with geographic coordinates."""
    barangay: Optional[str] = ""
    municipality_city: Optional[str] = ""
    province: Optional[str] = ""
    region: Optional[str] = ""
    latitude: Optional[str] = ""
    longitude: Optional[str] = ""


class AgentState(BaseModel):
    """LangGraph state object shared across all 5 pipeline nodes."""
    user_query: str
    intent: Optional[str] = None
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
