import re
import json
from prompts import SYSTEM_PROMPT, WEATHER_PROMPT
from tools.location_search import search_location
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


# Ambiguity detection 
def _detect_candidates(ref_lines: list[str]) -> list[dict] | None:
  """If multiple entries share the same level + parent, return them all.
  Returns None if every group has a single entry."""
  from collections import defaultdict

  groups: dict[str, list[dict]] = defaultdict(list)

  for line in ref_lines:
    if not line.startswith("["):
      continue
    level_end = line.index("]")
    level = line[1:level_end]
    parts = [p.strip() for p in line[level_end + 1:].split("|")]

    if level == "barangay" and len(parts) >= 6:
      key = f"{level}|{parts[1]}|{parts[2]}"
      groups[key].append({
        "barangay": parts[0],
        "municipality_city": parts[1],
        "province": parts[2],
        "region": parts[3],
        "latitude": parts[4],
        "longitude": parts[5],
      })
    elif level == "municipality_city" and len(parts) >= 5:
      key = f"{level}|{parts[1]}"
      groups[key].append({
        "municipality_city": parts[0],
        "province": parts[1],
        "region": parts[2],
        "latitude": parts[3],
        "longitude": parts[4],
      })

  for entries in groups.values():
    if len(entries) > 1:
      return entries

  return None

# Helper
def _prompt_distinguishes(prompt: str, picked: str, candidates: list[dict]) -> bool:
  """Check if the prompt contains a word unique to the picked candidate."""
  prompt_words = set(prompt.lower().replace(",", " ").split())
  picked_words = set(picked.lower().replace("(", "").replace(")", "").split())

  other_words: set[str] = set()
  picked_lower = picked.lower()
  for c in candidates:
    name = list(c.values())[0].lower()
    if name == picked_lower:
      continue  # skip the picked candidate
    other_words.update(name.replace("(", "").replace(")", "").split())

  unique = picked_words - other_words
  return bool(unique & prompt_words)

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

  # Extract loc & coords
  def prompt_to_location(self, prompt: str) -> dict:
    ref_lines = search_location(prompt)
    ref_text = "\n".join(ref_lines) if ref_lines else "(no reference data found)"

    # Check ambiguous
    ambiguous = _detect_candidates(ref_lines)

    location_prompt = (
      'Use this Philippine PSGC reference data to extract the location '
      'from the prompt. The reference shows valid names at each admin level.\n'
      'Fill ONLY the relevant fields in this JSON template. '
      'Leave unused fields as empty strings. '
      'If multiple entries match and the prompt does NOT specify which one '
      '(e.g. "San Agustin" without I or II), pick the FIRST match as your '
      'best guess. Return ONLY the JSON — no markdown, no explanation.\n\n'
      'Template: {"barangay": "", "municipality_city": "", "province": "",'
      ' "region": "", "latitude": "", "longitude": ""}\n\n'
      f'Reference data:\n{ref_text}\n\n'
      f'Prompt: {prompt}'
    )

    try:
      response = self.llm.invoke(location_prompt)
      raw_json = self._extract_json(response)
      if raw_json:
        result = json.loads(raw_json)
        result = {k: v for k, v in result.items() if v and isinstance(v, str)}
        if ambiguous:
          # Drop candidates if specifies
          picked = result.get("barangay") or result.get("municipality_city") or ""
          if _prompt_distinguishes(prompt, picked, ambiguous):
            pass
          else:
            result["candidates"] = ambiguous
        return result
    except (json.JSONDecodeError, Exception):
      pass

    return {}

  @staticmethod
  def _extract_json(text: str) -> str | None:
    """Robust JSON extraction — handles markdown fences, trailing prose."""
    text = text.strip()

    try:
      json.loads(text)
      return text
    except json.JSONDecodeError:
      pass

    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if md_match:
      return md_match.group(1).strip()

    start = text.find('{')
    if start == -1:
      return None
    depth = 0
    for i in range(start, len(text)):
      if text[i] == '{':
        depth += 1
      elif text[i] == '}':
        depth -= 1
        if depth == 0:
          return text[start:i + 1]

    return None

  @staticmethod
  def location_to_display_string(location: dict) -> str:
    """Format a location dict into a human-readable display string."""
    parts = []
    for key in ("barangay", "municipality_city", "province", "region"):
      if key in location and location[key]:
        parts.append(location[key])
    return ", ".join(parts)
