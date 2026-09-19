"""Public Open-Meteo & Time tools (No API key required)."""
import requests
from datetime import datetime
from typing import Dict, Any, Optional

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

def get_city_weather_and_time(city: str) -> Dict[str, Any]:
    """Get current weather conditions and local time for a city using Open-Meteo API.
    
    Args:
        city: Name of the city (e.g. 'Tokyo', 'London', 'San Francisco')
    
    Returns:
        Dictionary with location, local_time, temperature_c, humidity_percent, 
        condition, wind_speed_kmh, and status.
    """
    clean_city = city.strip()
    if not clean_city:
        return {"error": "City name must not be empty", "status": "error"}

    try:
        # Step 1: Geocoding lookup
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_city}&count=1&language=en&format=json"
        geo_resp = requests.get(geo_url, timeout=10)
        if geo_resp.status_code != 200:
            return {"error": f"Geocoding service returned HTTP {geo_resp.status_code}", "status": "error"}
        
        geo_data = geo_resp.json()
        results = geo_data.get("results")
        if not results:
            return {"error": f"City '{clean_city}' could not be located.", "status": "not_found"}
        
        loc = results[0]
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        resolved_name = loc.get("name", clean_city)
        country = loc.get("country", "")
        admin1 = loc.get("admin1", "")
        timezone_str = loc.get("timezone", "auto")

        # Step 2: Weather and local time query
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
            f"&timezone={timezone_str}"
        )
        w_resp = requests.get(weather_url, timeout=10)
        if w_resp.status_code != 200:
            return {"error": f"Weather service returned HTTP {w_resp.status_code}", "status": "error"}
        
        w_data = w_resp.json()
        current = w_data.get("current", {})
        temp = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")
        code = current.get("weather_code", 0)
        wind = current.get("wind_speed_10m")
        local_time = current.get("time", datetime.now().isoformat())
        condition = WEATHER_CODES.get(code, f"Weather code {code}")

        return {
            "city": resolved_name,
            "region": admin1,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "timezone": timezone_str,
            "local_time": local_time,
            "temperature_c": temp,
            "temperature_f": round((temp * 9 / 5) + 32, 1) if temp is not None else None,
            "humidity_percent": humidity,
            "condition": condition,
            "wind_speed_kmh": wind,
            "status": "success",
        }
    except Exception as e:
        return {"error": str(e), "status": "error"}

# Alias for backward/direct compatibility
get_weather = get_city_weather_and_time
get_current_weather = get_city_weather_and_time
