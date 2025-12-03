"""
Weather Fetcher - Gets weather data from Open-Meteo API

Open-Meteo is a FREE weather API that requires NO API key.
- Marine API: wave data
- Weather API: wind, temperature, precipitation, visibility
"""

import requests
from datetime import datetime
from typing import List
from models import Coordinates, Waypoint, WaypointWeather


# API endpoints (free, no API key needed!)
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"


def ms_to_knots(ms: float) -> float:
    """Convert meters/second to knots"""
    return ms * 1.944


def fetch_weather_for_point(position: Coordinates, date_time: str) -> WaypointWeather:
    """
    Fetch weather data for a single coordinate and time.
    
    Makes two API calls:
    1. Marine API - for wave data
    2. Weather API - for wind, temp, etc.
    
    Args:
        position: Lat/lng coordinates
        date_time: ISO format datetime string
        
    Returns:
        WaypointWeather with all conditions
    """
    dt = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
    date_str = dt.strftime('%Y-%m-%d')
    hour = dt.hour
    
    try:
        # Fetch marine data (waves)
        marine_response = requests.get(MARINE_API_URL, params={
            'latitude': position.lat,
            'longitude': position.lng,
            'hourly': 'wave_height,wind_wave_height,swell_wave_height',
            'start_date': date_str,
            'end_date': date_str
        }, timeout=10)
        marine_data = marine_response.json() if marine_response.ok else {}
        
        # Fetch weather data (wind, temp, etc.)
        weather_response = requests.get(WEATHER_API_URL, params={
            'latitude': position.lat,
            'longitude': position.lng,
            'hourly': 'temperature_2m,precipitation,visibility,wind_speed_10m,wind_direction_10m',
            'start_date': date_str,
            'end_date': date_str
        }, timeout=10)
        weather_data = weather_response.json() if weather_response.ok else {}
        
        # Extract data for the specific hour (with safe fallbacks)
        hour_index = min(hour, 23)
        
        # Get wave height (try multiple sources)
        wave_height = 1.0  # default
        if 'hourly' in marine_data and marine_data['hourly'].get('wave_height'):
            waves = marine_data['hourly']['wave_height']
            if hour_index < len(waves) and waves[hour_index] is not None:
                wave_height = waves[hour_index]
        
        # Get weather values
        hourly = weather_data.get('hourly', {})
        
        wind_speed_ms = _get_hourly_value(hourly, 'wind_speed_10m', hour_index, 5.0)
        wind_direction = _get_hourly_value(hourly, 'wind_direction_10m', hour_index, 180)
        precipitation = _get_hourly_value(hourly, 'precipitation', hour_index, 0)
        visibility_m = _get_hourly_value(hourly, 'visibility', hour_index, 10000)
        temperature = _get_hourly_value(hourly, 'temperature_2m', hour_index, 20)
        
        return WaypointWeather(
            wind_speed=round(ms_to_knots(wind_speed_ms), 1),
            wind_direction=round(wind_direction),
            wave_height=round(wave_height, 1),
            precipitation=round(precipitation, 1),
            visibility=round(visibility_m / 1000),  # Convert m to km
            temperature=round(temperature)
        )
        
    except Exception as e:
        # Return default weather if API fails
        print(f"  Warning: Weather fetch failed for {position.lat}, {position.lng}: {e}")
        return _get_default_weather()


def _get_hourly_value(hourly: dict, key: str, hour_index: int, default: float) -> float:
    """Safely get a value from hourly data with fallback."""
    if key in hourly and hourly[key]:
        values = hourly[key]
        if hour_index < len(values) and values[hour_index] is not None:
            return values[hour_index]
    return default


def _get_default_weather() -> WaypointWeather:
    """Return default weather when API is unavailable."""
    return WaypointWeather(
        wind_speed=12.0,
        wind_direction=180,
        wave_height=1.2,
        precipitation=0,
        visibility=15,
        temperature=18
    )


def fetch_weather_for_waypoints(waypoints: List[Waypoint]) -> List[Waypoint]:
    """
    Fetch weather for all waypoints in a route.
    
    Args:
        waypoints: List of waypoints (without weather)
        
    Returns:
        List of waypoints with weather data attached
    """
    print(f"  Fetching weather for {len(waypoints)} waypoints...")
    
    updated_waypoints = []
    
    for wp in waypoints:
        weather = fetch_weather_for_point(wp.position, wp.estimated_arrival)
        updated_waypoints.append(Waypoint(
            position=wp.position,
            estimated_arrival=wp.estimated_arrival,
            weather=weather
        ))
    
    return updated_waypoints


def summarize_weather(waypoints: List[Waypoint]) -> dict:
    """
    Get summary statistics for weather along a route.
    
    Returns dict with:
    - avg_wind_speed, max_wind_speed
    - avg_wave_height, max_wave_height
    - has_rain
    - avg_visibility
    """
    weathers = [wp.weather for wp in waypoints if wp.weather is not None]
    
    if not weathers:
        return {
            'avg_wind_speed': 0,
            'max_wind_speed': 0,
            'avg_wave_height': 0,
            'max_wave_height': 0,
            'has_rain': False,
            'avg_visibility': 10
        }
    
    wind_speeds = [w.wind_speed for w in weathers]
    wave_heights = [w.wave_height for w in weathers]
    visibilities = [w.visibility for w in weathers]
    
    return {
        'avg_wind_speed': round(sum(wind_speeds) / len(wind_speeds), 1),
        'max_wind_speed': round(max(wind_speeds), 1),
        'avg_wave_height': round(sum(wave_heights) / len(wave_heights), 1),
        'max_wave_height': round(max(wave_heights), 1),
        'has_rain': any(w.precipitation > 0.5 for w in weathers),
        'avg_visibility': round(sum(visibilities) / len(visibilities))
    }

