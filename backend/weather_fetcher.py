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
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from models import Coordinates, Waypoint, WaypointWeather
import math

# Set up logging
logger = logging.getLogger(__name__)


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
    
    logger.warning(f"  Fetching weather for {len(waypoints)} waypoints (batched, model: {model_name.upper()})...")
    
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
            logger.warning(f"  Warning: Weather API returned status {weather_response.status_code}")
    except Exception as e:
        logger.warning(f"  Warning: Weather API call failed: {e}")
    
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
            logger.warning(f"  Warning: Marine API returned status {marine_response.status_code}")
    except Exception as e:
        logger.warning(f"  Warning: Marine API call failed: {e}")
    
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
        logger.warning(f"  Warning: Failed to extract weather: {e}")
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


# ============================================================================
# Regional Weather Grid Functions (Phase 5A - Smart Routing)
# ============================================================================

def calculate_forecast_hours_needed(distance_nm: float, avg_boat_speed: float, buffer_multiplier: float = 1.5) -> int:
    """
    Calculate how many hours of weather forecast are needed for a route.
    
    This prevents wasting API calls and memory by fetching only what's needed.
    
    Args:
        distance_nm: Route distance in nautical miles
        avg_boat_speed: Expected average boat speed in knots
        buffer_multiplier: Safety multiplier (default: 1.5 = 50% extra time)
        
    Returns:
        Number of forecast hours needed (minimum 12, maximum 336 = 2 weeks)
        
    Example:
        100nm route at 6 knots = 16.7 hours
        With 1.5x buffer = 25 hours
        Returns: 25
    """
    import math
    
    if avg_boat_speed <= 0:
        avg_boat_speed = 5.0  # Fallback to conservative speed
    
    estimated_hours = distance_nm / avg_boat_speed
    forecast_hours = math.ceil(estimated_hours * buffer_multiplier)
    
    # Clamp to reasonable range
    forecast_hours = max(12, min(336, forecast_hours))  # 12 hours to 2 weeks
    
    return forecast_hours


def fetch_regional_weather_grid(
    start: Coordinates,
    end: Coordinates,
    departure_time: str,
    grid_spacing: float = 10.0,
    forecast_hours: int = 50
) -> Dict[str, Any]:
    """
    Fetch weather data for a grid of points covering the route area.
    
    This is used by wind routing algorithms to get weather for arbitrary points
    along potential routes, not just pre-defined waypoints.
    
    Args:
        start: Starting coordinates
        end: Ending coordinates
        departure_time: ISO 8601 departure time
        grid_spacing: Distance between grid points in nautical miles (default: 10nm)
        forecast_hours: How many hours of forecast to fetch (default: 50 hours)
        
    Returns:
        Dictionary with:
        - 'grid_points': List of (lat, lng) tuples
        - 'times': List of datetime objects for each forecast hour
        - 'weather_data': Dict[(lat, lng, time_index)] -> WaypointWeather
        - 'bounds': Dict with min_lat, max_lat, min_lng, max_lng
    
    TODO: ALWAYS calculate and pass forecast_hours based on estimated route duration!
          Don't rely on the default value to avoid wasting API calls and memory.
          Formula: forecast_hours = ceil(estimated_route_duration_hours * 1.5)
          The 1.5 multiplier provides buffer for slower-than-expected progress.
    """
    logger.warning(f"  Fetching regional weather grid (spacing: {grid_spacing}nm)...")
    
    # Calculate bounding box with 0.5° padding (about 30 nautical miles)
    min_lat = min(start.lat, end.lat) - 0.5
    max_lat = max(start.lat, end.lat) + 0.5
    min_lng = min(start.lng, end.lng) - 0.5
    max_lng = max(start.lng, end.lng) + 0.5
    
    # Convert grid spacing from nautical miles to degrees
    # 1 degree latitude ≈ 60 nautical miles
    # Longitude varies by latitude, use average latitude for conversion
    avg_lat = (min_lat + max_lat) / 2
    lat_spacing = grid_spacing / 60.0
    lng_spacing = grid_spacing / (60.0 * math.cos(math.radians(avg_lat)))
    
    # Generate grid points
    grid_points = []
    lat = min_lat
    while lat <= max_lat:
        lng = min_lng
        while lng <= max_lng:
            grid_points.append((round(lat, 4), round(lng, 4)))
            lng += lng_spacing
        lat += lat_spacing
    
    logger.warning(f"  Grid: {len(grid_points)} points covering {max_lat-min_lat:.2f}° lat × {max_lng-min_lng:.2f}° lng")
    
    # Parse departure time and calculate time range
    # NOTE: forecast_hours should be calculated based on route duration to minimize API calls!
    # Memory usage = grid_points × forecast_hours × ~100 bytes per weather object
    dept_dt = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
    end_dt = dept_dt + timedelta(hours=forecast_hours)
    start_date = dept_dt.strftime('%Y-%m-%d')
    end_date = end_dt.strftime('%Y-%m-%d')
    
    # Generate list of forecast times (hourly)
    times = [dept_dt + timedelta(hours=i) for i in range(forecast_hours + 1)]
    
    # Select best weather model based on route location
    model_name, weather_api_url = select_weather_model(avg_lat, (min_lng + max_lng) / 2)
    logger.warning(f"  Using weather model: {model_name.upper()}")
    
    # Prepare coordinates for batched API call
    # Open-Meteo supports up to 100 locations per request, so we may need multiple calls
    MAX_LOCATIONS_PER_REQUEST = 100
    
    weather_data = {}
    
    # Split grid points into chunks if needed
    for chunk_start in range(0, len(grid_points), MAX_LOCATIONS_PER_REQUEST):
        chunk = grid_points[chunk_start:chunk_start + MAX_LOCATIONS_PER_REQUEST]
        
        lat_str = ','.join(str(lat) for lat, lng in chunk)
        lng_str = ','.join(str(lng) for lat, lng in chunk)
        
        try:
            # Fetch weather data
            weather_response = requests.get(weather_api_url, params={
                'latitude': lat_str,
                'longitude': lng_str,
                'hourly': 'temperature_2m,precipitation,visibility,wind_speed_10m,wind_direction_10m,wind_gusts_10m',
                'start_date': start_date,
                'end_date': end_date
            }, timeout=30)
            
            if not weather_response.ok:
                logger.warning(f"  Warning: Weather API returned status {weather_response.status_code}")
                continue
                
            response_data = weather_response.json()
            
            # Fetch marine data (waves)
            marine_response = requests.get(MARINE_API_URL, params={
                'latitude': lat_str,
                'longitude': lng_str,
                'hourly': 'wave_height',
                'start_date': start_date,
                'end_date': end_date
            }, timeout=30)
            
            marine_response_data = marine_response.json() if marine_response.ok else []
            
            # Process response - Open-Meteo returns list of results for batched requests
            is_batched = isinstance(response_data, list)
            is_marine_batched = isinstance(marine_response_data, list)
            
            for i, (lat, lng) in enumerate(chunk):
                point_weather = response_data[i] if is_batched and i < len(response_data) else response_data
                point_marine = marine_response_data[i] if is_marine_batched and i < len(marine_response_data) else marine_response_data
                
                # Extract hourly data for this point
                hourly = point_weather.get('hourly', {})
                marine_hourly = point_marine.get('hourly', {})
                
                # Store weather for each time step
                for time_idx, time_dt in enumerate(times):
                    if time_idx >= len(hourly.get('time', [])):
                        break
                        
                    weather = _extract_weather_at_time_index(hourly, marine_hourly, time_idx)
                    weather_data[(lat, lng, time_idx)] = weather
                    
        except Exception as e:
            logger.warning(f"  Warning: Failed to fetch weather for grid chunk: {e}")
            continue
    
    logger.warning(f"  [OK] Fetched weather for {len(weather_data)} grid point-time combinations")
    
    return {
        'grid_points': grid_points,
        'times': times,
        'weather_data': weather_data,
        'bounds': {
            'min_lat': min_lat,
            'max_lat': max_lat,
            'min_lng': min_lng,
            'max_lng': max_lng
        }
    }


def interpolate_weather(
    position: Coordinates,
    time: datetime,
    weather_grid: Dict[str, Any]
) -> WaypointWeather:
    """
    Interpolate weather at an arbitrary position and time using the weather grid.
    
    Uses bilinear interpolation in space and linear interpolation in time.
    
    Args:
        position: Target position
        time: Target time
        weather_grid: Weather grid from fetch_regional_weather_grid()
        
    Returns:
        Interpolated WaypointWeather object
    """
    grid_points = weather_grid['grid_points']
    times = weather_grid['times']
    weather_data = weather_grid['weather_data']
    
    # Find time indices for temporal interpolation
    if time <= times[0]:
        time_idx = 0
        time_weight = 0.0
    elif time >= times[-1]:
        time_idx = len(times) - 2
        time_weight = 1.0
    else:
        # Find bracketing times
        for i in range(len(times) - 1):
            if times[i] <= time <= times[i + 1]:
                time_idx = i
                total_seconds = (times[i + 1] - times[i]).total_seconds()
                elapsed_seconds = (time - times[i]).total_seconds()
                time_weight = elapsed_seconds / total_seconds if total_seconds > 0 else 0.0
                break
        else:
            time_idx = 0
            time_weight = 0.0
    
    # Find 4 nearest grid points for spatial interpolation
    # Sort all points by distance to find closest ones
    distances = []
    for lat, lng in grid_points:
        dist = math.sqrt((lat - position.lat)**2 + (lng - position.lng)**2)
        distances.append((dist, lat, lng))
    
    distances.sort()
    
    # Use 4 closest points for bilinear interpolation
    # If we have exactly aligned grid, use proper bilinear interpolation
    # Otherwise, use distance-weighted interpolation
    closest_points = distances[:4]
    
    if not closest_points:
        # No grid data available, return default
        return _get_default_weather()
    
    # Distance-weighted interpolation
    total_weight = 0.0
    weighted_values = {
        'wind_speed': 0.0,
        'wind_direction_sin': 0.0,  # Use sin/cos for circular interpolation
        'wind_direction_cos': 0.0,
        'wave_height': 0.0,
        'precipitation': 0.0,
        'visibility': 0.0,
        'temperature': 0.0,
        'wind_gusts': 0.0,
        'wind_sustained': 0.0
    }
    
    for dist, lat, lng in closest_points:
        # Get weather at this point for both time indices
        weather_t0_key = (lat, lng, time_idx)
        weather_t1_key = (lat, lng, time_idx + 1)
        
        weather_t0 = weather_data.get(weather_t0_key)
        weather_t1 = weather_data.get(weather_t1_key)
        
        if not weather_t0:
            continue
            
        # Temporal interpolation
        if weather_t1 and time_weight > 0:
            wind_speed = weather_t0.wind_speed * (1 - time_weight) + weather_t1.wind_speed * time_weight
            wave_height = weather_t0.wave_height * (1 - time_weight) + weather_t1.wave_height * time_weight
            precipitation = weather_t0.precipitation * (1 - time_weight) + weather_t1.precipitation * time_weight
            visibility = weather_t0.visibility * (1 - time_weight) + weather_t1.visibility * time_weight
            temperature = weather_t0.temperature * (1 - time_weight) + weather_t1.temperature * time_weight
            wind_gusts = weather_t0.wind_gusts * (1 - time_weight) + weather_t1.wind_gusts * time_weight
            wind_sustained = weather_t0.wind_sustained * (1 - time_weight) + weather_t1.wind_sustained * time_weight
            
            # Interpolate wind direction using circular mean
            dir0_rad = math.radians(weather_t0.wind_direction)
            dir1_rad = math.radians(weather_t1.wind_direction)
            wind_dir_sin = math.sin(dir0_rad) * (1 - time_weight) + math.sin(dir1_rad) * time_weight
            wind_dir_cos = math.cos(dir0_rad) * (1 - time_weight) + math.cos(dir1_rad) * time_weight
        else:
            wind_speed = weather_t0.wind_speed
            wave_height = weather_t0.wave_height
            precipitation = weather_t0.precipitation
            visibility = weather_t0.visibility
            temperature = weather_t0.temperature
            wind_gusts = weather_t0.wind_gusts
            wind_sustained = weather_t0.wind_sustained
            wind_dir_sin = math.sin(math.radians(weather_t0.wind_direction))
            wind_dir_cos = math.cos(math.radians(weather_t0.wind_direction))
        
        # Spatial interpolation weight (inverse distance, avoid division by zero)
        weight = 1.0 / (dist + 0.001)
        
        weighted_values['wind_speed'] += wind_speed * weight
        weighted_values['wind_direction_sin'] += wind_dir_sin * weight
        weighted_values['wind_direction_cos'] += wind_dir_cos * weight
        weighted_values['wave_height'] += wave_height * weight
        weighted_values['precipitation'] += precipitation * weight
        weighted_values['visibility'] += visibility * weight
        weighted_values['temperature'] += temperature * weight
        weighted_values['wind_gusts'] += wind_gusts * weight
        weighted_values['wind_sustained'] += wind_sustained * weight
        
        total_weight += weight
    
    if total_weight == 0:
        return _get_default_weather()
    
    # Normalize by total weight
    for key in weighted_values:
        weighted_values[key] /= total_weight
    
    # Convert wind direction back from sin/cos
    wind_direction = math.degrees(math.atan2(
        weighted_values['wind_direction_sin'],
        weighted_values['wind_direction_cos']
    ))
    if wind_direction < 0:
        wind_direction += 360
    
    return WaypointWeather(
        wind_speed=round(weighted_values['wind_speed'], 1),
        wind_direction=round(wind_direction),
        wave_height=round(weighted_values['wave_height'], 1),
        precipitation=round(weighted_values['precipitation'], 1),
        visibility=round(weighted_values['visibility']),
        temperature=round(weighted_values['temperature']),
        wind_gusts=round(weighted_values['wind_gusts'], 1),
        wind_sustained=round(weighted_values['wind_sustained'], 1)
    )


def _extract_weather_at_time_index(
    hourly: Dict[str, Any],
    marine_hourly: Dict[str, Any],
    time_idx: int
) -> WaypointWeather:
    """
    Extract weather data at a specific time index from API response.
    
    Helper function for grid weather extraction.
    """
    # Get wave height
    wave_height = 1.0
    if 'wave_height' in marine_hourly and marine_hourly['wave_height']:
        waves = marine_hourly['wave_height']
        if time_idx < len(waves) and waves[time_idx] is not None:
            wave_height = waves[time_idx]
    
    # Get wind data (km/h from API)
    wind_speed_kmh = _get_hourly_value(hourly, 'wind_speed_10m', time_idx, 15.0)
    wind_gusts_kmh = _get_hourly_value(hourly, 'wind_gusts_10m', time_idx, wind_speed_kmh * 1.3)
    wind_direction = _get_hourly_value(hourly, 'wind_direction_10m', time_idx, 180)
    
    # Convert to knots
    wind_sustained_kt = kmh_to_knots(wind_speed_kmh)
    wind_gusts_kt = kmh_to_knots(wind_gusts_kmh)
    
    # Calculate effective wind (blend sustained + gusts)
    effective_wind_kt = calculate_effective_wind(wind_sustained_kt, wind_gusts_kt)
    
    # Other weather data
    precipitation = _get_hourly_value(hourly, 'precipitation', time_idx, 0)
    visibility_m = _get_hourly_value(hourly, 'visibility', time_idx, 10000)
    temperature = _get_hourly_value(hourly, 'temperature_2m', time_idx, 20)
    
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
