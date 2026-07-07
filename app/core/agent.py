import re
from prompts import SYSTEM_PROMPT, WEATHER_PROMPT
EMAIL_REGEX = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
PHONE_REGEX = r"(\+?\d[\d -]{8,}\d)"
CREDIT_CARD_REGEX = r"\b(?:\d[ -]*?){13,16}\b"

# Blocked phrases indicating prompt injection
INJECTION_PATTERNS = ["ignore previous", "system prompt", "act as", "jailbreak", "bypass", "override"]

# Keywords to ensure the topic is weather-related
WEATHER_KEYWORDS = ["weather", "forecast", "temperature", "rain", "humidity", "wind", "storm", "typhoon", "heat", "climate", "uv", "visibility", "pressure", "el nino", "la nina"]

# Keywords to block
FARMING_ADVICE_KEYWORDS = ["what to plant", "when to plant", "fertilizer", "pesticide", "harvesting schedule", "crop yield"]

def remove_pii(text: str) -> str:
  text = re.sub(EMAIL_REGEX, "[EMAIL REDACTED]", text)
  text = re.sub(PHONE_REGEX, "[PHONE REDACTED]", text)
  text = re.sub(CREDIT_CARD_REGEX, "[CARD REDACTED]", text)
  return text

def detect_prompt_injection(text: str) -> bool:
  lower_text = text.lower()
  for pattern in INJECTION_PATTERNS:
    if pattern in lower_text:
      return True
  return False

def is_weather_related(text: str) -> bool:
  lower_text = text.lower()
  for word in WEATHER_KEYWORDS:
    if word in lower_text:
      return True
  return False

def requests_farming_advice(text: str) -> bool:
  lower_text = text.lower()
  for word in FARMING_ADVICE_KEYWORDS:
    if word in lower_text:
      return True
  return False

def validate_output(answer: str) -> str:
  banned_words = ["I think", "probably", "maybe", "I guess", "approximately"]
  for word in banned_words:
    answer = answer.replace(word, "")
  return answer.strip()

class WeatherAgent:
  def __init__(self, llm):
    self.llm = llm

  def build_prompt(self, question: str, location: str, weather_data: str) -> str:
    formatted_user_prompt = WEATHER_PROMPT.format(question=question, location=location, weather_data=weather_data)
    return SYSTEM_PROMPT + "\n\n" + formatted_user_prompt

  def run(self, question: str, location: str, weather_data: str) -> str:
    if not question.strip():
      return "Please enter a weather-related question."

    question = remove_pii(question)

    if detect_prompt_injection(question):
      return "Request blocked. Please ask a standard weather-related question."

    if not is_weather_related(question):
      return "I can only answer questions related to weather conditions and forecasts."

    if requests_farming_advice(question):
      return "I am a weather assistant and cannot provide farming, planting, or crop management advice. Please consult an agricultural expert."

    prompt = self.build_prompt(question, location, weather_data)

    try:
      llm_output = self.llm.invoke(prompt)
    except Exception as e:
      return "An error occurred while communicating with the model engine."

    final_output = validate_output(llm_output)

    if not final_output:
      return "No weather information could be generated from the available data."

    return final_output
