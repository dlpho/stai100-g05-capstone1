from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union

# MODULE 2 - STRUCTURED OUTPUTS (PYDANTIC)
class MessageDict(BaseModel):
    role: str
    content: str

class UserQuery(BaseModel):
    user_query: str
    history: Optional[List[MessageDict]] = []

class LocationEntity(BaseModel):
    barangay: Optional[str] = ""
    municipality_city: Optional[str] = ""
    province: Optional[str] = ""
    region: Optional[str] = ""
    latitude: Optional[str] = ""
    longitude: Optional[str] = ""

class AgentState(BaseModel):
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
