"""
Weather Fetcher - Gets weather data from Open-Meteo API

Open-Meteo is a FREE weather API that requires NO API key.
- Marine API: wave data
- Weather API: wind, temperature, precipitation, visibility

FEATURES:
- Auto-selects best weather model based on region (ECMWF for Europe/Med, GFS for Americas)
- Uses batched API calls (2 requests instead of 12 per route)
- Blends sustained wind + gusts for effective wind speed
"""

import requests
from datetime import datetime
from typing import List, Dict, Any, Tuple
from models import Coordinates, Waypoint, WaypointWeather


# API endpoints (free, no API key needed!)
MARINE_API_URL = "https://marine-api.open-meteo.com/v1/marine"

# Weather API endpoints for different models
WEATHER_APIS = {
    'default': "https://api.open-meteo.com/v1/forecast",
    'ecmwf': "https://api.open-meteo.com/v1/ecmwf",      # European model - best for Europe/Med
    'gfs': "https://api.open-meteo.com/v1/gfs",          # US NOAA model - best for Americas
}


def kmh_to_knots(kmh: float) -> float:
    """Convert kilometers/hour to knots (the API returns km/h by default)"""
    return kmh * 0.539957


def select_weather_model(lat: float, lng: float) -> Tuple[str, str]:
    """
    Select the best weather model based on geographic location.
    
    Returns:
        Tuple of (model_name, api_url)
    
    Model selection:
    - ECMWF: Europe, Mediterranean, Middle East, Africa (best high-resolution for these areas)
    - GFS: Americas, Pacific, default fallback
    """
    # ECMWF is best for: Europe, Mediterranean, Middle East, Africa
    # Roughly: longitude -30 to 60, latitude -40 to 75
    if -30 <= lng <= 60 and -40 <= lat <= 75:
        return ('ecmwf', WEATHER_APIS['ecmwf'])
    
    # GFS for Americas and rest of world
    return ('gfs', WEATHER_APIS['gfs'])


def calculate_effective_wind(sustained: float, gusts: float) -> float:
    """
    Calculate effective wind speed by blending sustained wind and gusts.
    
    For sailing, you need to account for gusts - they affect boat handling
    and safety more than average wind alone.
    
    Formula: 70% sustained + 30% gusts
    This gives a realistic "felt" wind that sailors experience.
    """
    if gusts <= 0:
        return sustained
    return (sustained * 0.7) + (gusts * 0.3)


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
        temperature=18,
        wind_gusts=15.0,
        wind_sustained=10.0,
        is_estimated=True
    )


def fetch_weather_for_waypoints(waypoints: List[Waypoint]) -> List[Waypoint]:
    """
    Fetch weather for all waypoints in a route using BATCHED API calls.
    
    Features:
    - Auto-selects best weather model based on route location
    - Fetches wind gusts for realistic wind assessment
    - Makes only 2 API calls total (1 marine + 1 weather)
    
    Args:
        waypoints: List of waypoints (without weather)
        
    Returns:
        List of waypoints with weather data attached
    """
    if not waypoints:
        return []
    
    # Extract coordinates and times
    latitudes = [wp.position.lat for wp in waypoints]
    longitudes = [wp.position.lng for wp in waypoints]
    
    # Select best model based on average position of route
    avg_lat = sum(latitudes) / len(latitudes)
    avg_lng = sum(longitudes) / len(longitudes)
    model_name, weather_api_url = select_weather_model(avg_lat, avg_lng)
    
    print(f"  Fetching weather for {len(waypoints)} waypoints (batched, model: {model_name.upper()})...")
    
    # Parse arrival times to get dates and hours
    arrival_times = []
    for wp in waypoints:
        dt = datetime.fromisoformat(wp.estimated_arrival.replace('Z', '+00:00'))
        arrival_times.append(dt)
    
    # Get date range for the request (start and end dates)
    dates = [dt.strftime('%Y-%m-%d') for dt in arrival_times]
    start_date = min(dates)
    end_date = max(dates)
    
    # Convert lists to comma-separated strings for API
    lat_str = ','.join(str(lat) for lat in latitudes)
    lng_str = ','.join(str(lng) for lng in longitudes)
    
    weather_data = {}
    marine_data = {}
    
    try:
        # Fetch weather data with wind gusts
        weather_response = requests.get(weather_api_url, params={
            'latitude': lat_str,
            'longitude': lng_str,
            'hourly': 'temperature_2m,precipitation,visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m',
            'start_date': start_date,
            'end_date': end_date
        }, timeout=15)
        
        if weather_response.ok:
            weather_data = weather_response.json()
        else:
            print(f"  Warning: Weather API returned status {weather_response.status_code}")
    except Exception as e:
        print(f"  Warning: Weather API call failed: {e}")
    
    try:
        # Fetch marine data (waves)
        marine_response = requests.get(MARINE_API_URL, params={
            'latitude': lat_str,
            'longitude': lng_str,
            'hourly': 'wave_height',
            'start_date': start_date,
            'end_date': end_date
        }, timeout=15)
        
        if marine_response.ok:
            marine_data = marine_response.json()
        else:
            print(f"  Warning: Marine API returned status {marine_response.status_code}")
    except Exception as e:
        print(f"  Warning: Marine API call failed: {e}")
    
    # Process response and create updated waypoints
    updated_waypoints = []
    
    # Check if we got batched response (list of results) or single point response (dict)
    is_batched_weather = isinstance(weather_data, list)
    is_batched_marine = isinstance(marine_data, list)
    
    for i, wp in enumerate(waypoints):
        hour_index = min(arrival_times[i].hour, 23)
        
        # Calculate day offset if route spans multiple days
        day_offset = (arrival_times[i].date() - datetime.fromisoformat(start_date).date()).days
        adjusted_hour = day_offset * 24 + hour_index
        
        if is_batched_weather or is_batched_marine:
            point_weather = weather_data[i] if is_batched_weather and i < len(weather_data) else {}
            point_marine = marine_data[i] if is_batched_marine and i < len(marine_data) else {}
            weather = _extract_weather_from_single(point_weather, point_marine, adjusted_hour)
        else:
            weather = _extract_weather_from_single(weather_data, marine_data, adjusted_hour)
        
        updated_waypoints.append(Waypoint(
            position=wp.position,
            estimated_arrival=wp.estimated_arrival,
            weather=weather
        ))
    
    return updated_waypoints


def _extract_weather_from_single(
    weather_data: Dict[str, Any],
    marine_data: Dict[str, Any],
    hour_index: int
) -> WaypointWeather:
    """Extract weather from single-point API response."""
    try:
        hourly = weather_data.get('hourly', {})
        
        # Get wave height
        wave_height = 1.0
        if 'hourly' in marine_data and marine_data['hourly'].get('wave_height'):
            waves = marine_data['hourly']['wave_height']
            if hour_index < len(waves) and waves[hour_index] is not None:
                wave_height = waves[hour_index]
        
        # Get wind data (km/h from API)
        wind_speed_kmh = _get_hourly_value(hourly, 'wind_speed_10m', hour_index, 15.0)
        wind_gusts_kmh = _get_hourly_value(hourly, 'wind_gusts_10m', hour_index, wind_speed_kmh * 1.3)
        wind_direction = _get_hourly_value(hourly, 'wind_direction_10m', hour_index, 180)
        
        # Convert to knots
        wind_sustained_kt = kmh_to_knots(wind_speed_kmh)
        wind_gusts_kt = kmh_to_knots(wind_gusts_kmh)
        
        # Calculate effective wind (blend sustained + gusts)
        effective_wind_kt = calculate_effective_wind(wind_sustained_kt, wind_gusts_kt)
        
        # Other weather data
        precipitation = _get_hourly_value(hourly, 'precipitation', hour_index, 0)
        visibility_m = _get_hourly_value(hourly, 'visibility', hour_index, 10000)
        temperature = _get_hourly_value(hourly, 'temperature_2m', hour_index, 20)
        
        return WaypointWeather(
            wind_speed=round(effective_wind_kt, 1),
            wind_direction=round(wind_direction),
            wave_height=round(wave_height, 1),
            precipitation=round(precipitation, 1),
            visibility=round(visibility_m / 1000),
            temperature=round(temperature),
            wind_gusts=round(wind_gusts_kt, 1),
            wind_sustained=round(wind_sustained_kt, 1)
        )
    except Exception as e:
        print(f"  Warning: Failed to extract weather: {e}")
        return _get_default_weather()


def summarize_weather(waypoints: List[Waypoint]) -> dict:
    """
    Get summary statistics for weather along a route.
    
    Returns dict with:
    - avg_wind_speed, max_wind_speed (effective wind)
    - avg_wave_height, max_wave_height
    - has_rain
    - avg_visibility
    - max_gusts
    """
    weathers = [wp.weather for wp in waypoints if wp.weather is not None]
    
    if not weathers:
        return {
            'avg_wind_speed': 0,
            'max_wind_speed': 0,
            'avg_wave_height': 0,
            'max_wave_height': 0,
            'has_rain': False,
            'avg_visibility': 10,
            'max_gusts': 0
        }
    
    wind_speeds = [w.wind_speed for w in weathers]
    wave_heights = [w.wave_height for w in weathers]
    visibilities = [w.visibility for w in weathers]
    gusts = [w.wind_gusts for w in weathers]
    
    return {
        'avg_wind_speed': round(sum(wind_speeds) / len(wind_speeds), 1),
        'max_wind_speed': round(max(wind_speeds), 1),
        'avg_wave_height': round(sum(wave_heights) / len(wave_heights), 1),
        'max_wave_height': round(max(wave_heights), 1),
        'has_rain': any(w.precipitation > 0.5 for w in weathers),
        'avg_visibility': round(sum(visibilities) / len(visibilities)),
        'max_gusts': round(max(gusts), 1)
    }
