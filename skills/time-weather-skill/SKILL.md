---
name: time-weather-skill
description: Get the current real-time weather and local time for any specified city or location worldwide without requiring any API key. Use this skill whenever the user asks about weather, temperature, forecasts, conditions, or the local time in a city.
triggers:
  - weather in [city]
  - what is the weather in [city]
  - temperature in [city]
  - current time in [city]
  - what time is it in [city]
  - forecast for [city]
---

# Time and Weather Skill

## Description
Provides real-time weather metrics (temperature, humidity, weather condition description, wind speed) and current local time for any city worldwide using the free Open-Meteo public service.

## SOP & Tool Execution
When the user asks for the weather or current time in a specific city:
1. Extract the `city` parameter from the user query (e.g., "Tokyo", "Paris", "New York", "San Francisco").
2. Invoke `env_tools.get_city_weather_and_time` with the extracted argument:
```json
{
  "tool": "env_tools.get_city_weather_and_time",
  "arguments": {
    "city": "Tokyo"
  }
}
```
3. Synthesize the returned structured data into a helpful response for the user.
