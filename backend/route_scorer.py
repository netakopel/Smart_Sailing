"""
Route Scorer - Calculates safety and efficiency scores for routes

Scoring is based on:
- Wind conditions (speed, angle relative to boat)
- Wave height
- Visibility
- Distance efficiency
"""

from typing import List, Tuple
from models import (
    Waypoint, Route, BoatProfile, BoatType, 
    BOAT_PROFILES, WaypointWeather, RouteType
)
from route_generator import GeneratedRoute, calculate_bearing
from weather_fetcher import summarize_weather


def calculate_wind_angle(boat_heading: float, wind_direction: float) -> float:
    """
    Calculate wind angle relative to boat heading.
    
    Args:
        boat_heading: Direction boat is traveling (degrees)
        wind_direction: Direction wind is coming FROM (degrees)
        
    Returns:
        Angle between 0-180 degrees
        - 0 = headwind (wind in your face)
        - 90 = beam reach (wind from side)
        - 180 = downwind (wind from behind)
    """
    # Wind direction is where wind comes FROM
    # Convert to where it's going TO
    wind_to = (wind_direction + 180) % 360
    
    angle = abs(boat_heading - wind_to)
    if angle > 180:
        angle = 360 - angle
    
    return angle


def score_wind_conditions(
    weather: WaypointWeather,
    boat_heading: float,
    boat: BoatProfile
) -> Tuple[float, List[str]]:
    """
    Score wind conditions for a route segment.
    
    Returns:
        Tuple of (score 0-100, list of notes)
    """
    notes = []
    score = 100.0
    
    wind_angle = calculate_wind_angle(boat_heading, weather.wind_direction)
    
    # For sailboats, wind angle matters a lot
    if boat.boat_type in [BoatType.SAILBOAT, BoatType.CATAMARAN]:
        # Too little wind = bad for sailing
        if weather.wind_speed < boat.min_wind_speed:
            score -= 30
            notes.append(f"Low wind ({weather.wind_speed}kt) - may need motor")
        
        # Headwind = slow and requires tacking
        if wind_angle < 45:
            score -= 25
            notes.append("Headwind - will need to tack")
        # Beam reach to broad reach = ideal for sailing
        elif 90 <= wind_angle <= 150:
            score += 10  # bonus!
    
    # High wind is dangerous for all boats
    if weather.wind_speed > boat.max_safe_wind_speed:
        score -= 40
        notes.append(f"Dangerous wind: {weather.wind_speed}kt exceeds safe limit")
    elif weather.wind_speed > boat.max_safe_wind_speed * 0.8:
        score -= 20
        notes.append(f"Strong wind: {weather.wind_speed}kt - challenging conditions")
    
    return max(0, min(100, score)), notes


def score_wave_conditions(
    wave_height: float,
    boat: BoatProfile
) -> Tuple[float, List[str]]:
    """Score wave conditions."""
    notes = []
    score = 100.0
    
    if wave_height > boat.max_safe_wave_height:
        score -= 40
        notes.append(f"Dangerous waves: {wave_height}m exceeds safe limit")
    elif wave_height > boat.max_safe_wave_height * 0.7:
        score -= 20
        notes.append(f"Rough seas: {wave_height}m waves")
    elif wave_height < 0.5:
        score += 5
        notes.append("Calm seas")
    
    return max(0, min(100, score)), notes


def score_visibility_conditions(weather: WaypointWeather) -> Tuple[float, List[str]]:
    """Score visibility and precipitation."""
    notes = []
    score = 100.0
    
    if weather.visibility < 2:
        score -= 30
        notes.append("Poor visibility - fog or heavy precipitation")
    elif weather.visibility < 5:
        score -= 15
        notes.append("Reduced visibility")
    
    if weather.precipitation > 5:
        score -= 20
        notes.append("Heavy rain expected")
    elif weather.precipitation > 1:
        score -= 10
        notes.append("Rain expected")
    
    return max(0, min(100, score)), notes


def score_distance(
    route_distance: float,
    direct_distance: float
) -> Tuple[float, List[str]]:
    """
    Score distance efficiency.
    Shorter routes get higher scores.
    """
    notes = []
    score = 100.0
    
    ratio = route_distance / direct_distance
    
    if ratio > 1.2:
        score -= 20
        notes.append(f"{int((ratio - 1) * 100)}% longer than direct route")
    elif ratio > 1.1:
        score -= 10
        notes.append(f"{int((ratio - 1) * 100)}% longer than direct route")
    elif ratio <= 1.02:
        notes.append("Most direct path")
    
    return score, notes


def calculate_segment_bearings(waypoints: List[Waypoint]) -> List[float]:
    """Calculate bearing for each segment of the route."""
    bearings = []
    for i in range(len(waypoints) - 1):
        bearing = calculate_bearing(
            waypoints[i].position,
            waypoints[i + 1].position
        )
        bearings.append(bearing)
    return bearings


def score_route(
    route: GeneratedRoute,
    boat_type: BoatType,
    direct_distance: float
) -> Route:
    """
    Main scoring function - scores a complete route.
    
    Combines scores from:
    - Wind conditions (35%)
    - Wave conditions (25%)
    - Visibility (15%)
    - Distance efficiency (25%)
    
    Args:
        route: Generated route with waypoints and weather
        boat_type: Type of boat
        direct_distance: Distance of direct route (for comparison)
        
    Returns:
        Complete Route object with score, warnings, pros, cons
    """
    boat = BOAT_PROFILES[boat_type]
    bearings = calculate_segment_bearings(route.waypoints)
    
    all_warnings = []
    all_pros = []
    all_cons = []
    
    total_wind_score = 0.0
    total_wave_score = 0.0
    total_visibility_score = 0.0
    segments_scored = 0
    
    # Track if any weather data is estimated (API failed)
    estimated_weather_count = 0
    
    # Score each waypoint/segment
    for i, waypoint in enumerate(route.waypoints):
        if waypoint.weather is None:
            continue
        
        # Check if this is estimated (default) weather data
        if waypoint.weather.is_estimated:
            estimated_weather_count += 1
        
        # Use bearing of the segment starting at this waypoint
        heading = bearings[min(i, len(bearings) - 1)] if bearings else 0
        
        # Wind scoring
        wind_score, wind_notes = score_wind_conditions(
            waypoint.weather, heading, boat
        )
        total_wind_score += wind_score
        
        # Wave scoring
        wave_score, wave_notes = score_wave_conditions(
            waypoint.weather.wave_height, boat
        )
        total_wave_score += wave_score
        
        # Visibility scoring
        vis_score, vis_notes = score_visibility_conditions(waypoint.weather)
        total_visibility_score += vis_score
        
        # Collect warnings (only unique, serious ones)
        for note in wind_notes + wave_notes + vis_notes:
            if ('Dangerous' in note or 'exceeds' in note) and note not in all_warnings:
                all_warnings.append(note)
        
        segments_scored += 1
    
    # Distance scoring
    distance_score, distance_notes = score_distance(route.distance, direct_distance)
    
    # Calculate averages
    avg_wind = total_wind_score / segments_scored if segments_scored > 0 else 50
    avg_wave = total_wave_score / segments_scored if segments_scored > 0 else 50
    avg_vis = total_visibility_score / segments_scored if segments_scored > 0 else 50
    
    # Weighted final score
    # Wind: 35%, Waves: 25%, Visibility: 15%, Distance: 25%
    final_score = int(
        avg_wind * 0.35 +
        avg_wave * 0.25 +
        avg_vis * 0.15 +
        distance_score * 0.25
    )
    
    # Generate pros and cons based on weather summary
    weather_summary = summarize_weather(route.waypoints)
    
    # Determine pros
    if 8 <= weather_summary['avg_wind_speed'] <= 20:
        all_pros.append("Good sailing wind")
    if weather_summary['avg_wave_height'] < 1:
        all_pros.append("Calm seas")
    if not weather_summary['has_rain']:
        all_pros.append("No rain expected")
    if route.route_type == RouteType.DIRECT:
        all_pros.append("Shortest distance")
    if weather_summary['avg_visibility'] > 15:
        all_pros.append("Excellent visibility")
    
    # Determine cons
    if weather_summary['avg_wind_speed'] < 5 and boat.boat_type == BoatType.SAILBOAT:
        all_cons.append("May need motor - low wind")
    if weather_summary['max_wave_height'] > 2:
        all_cons.append("Rough sections expected")
    if weather_summary['has_rain']:
        all_cons.append("Rain expected on route")
    if route.distance > direct_distance * 1.1:
        all_cons.append("Longer route")
    
    # Add warning if some weather data was estimated (API failed)
    if estimated_weather_count > 0:
        all_warnings.append(
            f"Weather data unavailable for {estimated_weather_count} waypoint(s) - using estimates"
        )
    
    # Ensure we always have at least one pro/con
    if not all_pros:
        all_pros = ["Standard conditions"]
    if not all_cons:
        all_cons = ["No significant concerns"]
    
    return Route(
        name=route.name,
        route_type=route.route_type,
        score=max(0, min(100, final_score)),
        distance=route.distance,
        estimated_time=route.estimated_time,
        estimated_hours=route.estimated_hours,
        waypoints=route.waypoints,
        warnings=all_warnings,
        pros=all_pros,
        cons=all_cons
    )

