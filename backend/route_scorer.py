"""
Route Scorer - Calculates safety and efficiency scores for routes

Scoring is based on:
- Wind conditions (speed, angle relative to boat)
- Wave height
- Visibility
- Distance efficiency
"""

import logging
from typing import List, Tuple
from models import (
    Waypoint, Route, BoatProfile, BoatType, 
    BOAT_PROFILES, WaypointWeather, RouteType
)
from route_generator import GeneratedRoute, calculate_bearing
from weather_fetcher import summarize_weather
from polars import is_in_no_go_zone, calculate_wind_angle as calculate_wind_angle_polar

# Set up logging
logger = logging.getLogger(__name__)


# NOTE: Using calculate_wind_angle from polars.py instead
# The function below was calculating opposite values and causing bugs
# def calculate_wind_angle(boat_heading: float, wind_direction: float) -> float:
#     """DEPRECATED - use calculate_wind_angle from polars.py"""
#     wind_to = (wind_direction + 180) % 360
#     angle = abs(boat_heading - wind_to)
#     if angle > 180:
#         angle = 360 - angle
#     return angle


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
    
    wind_angle = calculate_wind_angle_polar(boat_heading, weather.wind_direction)
    
    # For sailboats, wind angle matters a lot
    if boat.boat_type in [BoatType.SAILBOAT, BoatType.CATAMARAN]:
        # Too little wind = bad for sailing
        if weather.wind_speed < boat.min_wind_speed:
            score -= 30
            notes.append(f"Low wind ({weather.wind_speed}kt) - may need motor")
        
        # NO-GO ZONE: Heading into wind = boat can't sail efficiently or at all
        if wind_angle < 45:
            score -= 90  # MASSIVE penalty - boat essentially can't sail here
            # Note: NO-GO zone warnings now handled in frontend visualization, not here
        elif wind_angle < 60:
            score -= 50  # Still very poor sailing angle
            notes.append(f"Very close to wind ({wind_angle:.0f}°) - poor performance")
        # Beam reach to broad reach = ideal for sailing
        elif 90 <= wind_angle <= 150:
            score += 10  # bonus!
            notes.append(f"Good sailing angle ({wind_angle:.0f}°)")
    
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
    
    CRITICAL: Routes entering dangerous "no-go zones" receive severe penalties
    
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
    
    # Track no-go zone waypoints (sailing into wind) - should heavily penalize the route
    no_go_penalty = 0
    no_go_waypoints = 0
    
    # Track dangerous conditions (high wind/waves)
    danger_penalty = 0
    dangerous_waypoints = 0
    
    # Score each waypoint/segment
    for i, waypoint in enumerate(route.waypoints):
        if waypoint.weather is None:
            continue
        
        # Check if this is estimated (default) weather data
        if waypoint.weather.is_estimated:
            estimated_weather_count += 1
        
        # Use bearing of the segment starting at this waypoint
        heading = bearings[min(i, len(bearings) - 1)] if bearings else 0
        
        # Calculate wind angle for no-go zone detection (use polars.py function!)
        wind_angle = calculate_wind_angle_polar(heading, waypoint.weather.wind_direction)
        
        # DEBUG: Print wind angle info for sailboats/catamarans (disabled for cleaner output)
        # if boat.boat_type in [BoatType.SAILBOAT, BoatType.CATAMARAN]:
        #     print(f"      [DEBUG] WP{i}: heading={heading:.1f}°, wind_from={waypoint.weather.wind_direction:.1f}°, wind_angle={wind_angle:.1f}°")
        
        # Check if sailing in NO-GO ZONE (can't sail into wind)
        if is_in_no_go_zone(wind_angle, boat.boat_type.value):
            no_go_waypoints += 1
            # Very light penalty - only count waypoints for now
            # print(f"      [NO-GO ZONE] Wind angle: {wind_angle:.0f}°, Total waypoints: {no_go_waypoints}")
        
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
            if ('Dangerous' in note or 'exceeds' in note or 'NO-GO' in note) and note not in all_warnings:
                all_warnings.append(note)
        
        # Also check for dangerous conditions (high wind/waves/poor visibility)
        is_dangerous = False
        if waypoint.weather.wind_speed > boat.max_safe_wind_speed:
            is_dangerous = True
            danger_penalty += 80  # MASSIVE penalty - route should be disqualified
        if waypoint.weather.wave_height > boat.max_safe_wave_height:
            is_dangerous = True
            danger_penalty += 70  # MASSIVE penalty - route should be disqualified
        if waypoint.weather.visibility < 1:  # Very poor visibility
            is_dangerous = True
            danger_penalty += 40  # Heavy penalty
        
        if is_dangerous:
            dangerous_waypoints += 1
        
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
    
    # Apply very light no-go zone penalty - only if there are MANY waypoints in no-go zone
    if no_go_waypoints > 10:
        no_go_penalty = 20  # Light penalty - only for routes with 10+ no-go waypoints
    else:
        no_go_penalty = 0  # No penalty for routes with few no-go waypoints
    
    # Apply penalties
    logger.debug(f"   [SCORING] Base score: {final_score}, No-go waypoints: {no_go_waypoints}, No-go penalty: {no_go_penalty}, Danger penalty: {danger_penalty}")
    final_score -= no_go_penalty
    final_score -= danger_penalty
    logger.debug(f"   [SCORING] Final score after penalties: {final_score}")
    
    # Add warning if route has many no-go zone waypoints
    if no_go_waypoints > 5:
        all_cons.append(f"Some sailing into wind ({no_go_waypoints} waypoints)")
    
    if no_go_waypoints > 10:
        no_go_warning = f"Route sails into wind at {no_go_waypoints} waypoint(s)"
        all_warnings.append(no_go_warning)
    
    # Add warning if route goes through dangerous conditions
    if dangerous_waypoints > 0:
        danger_warning = f"DANGER: Route passes through {dangerous_waypoints} unsafe waypoint(s)"
        all_warnings.insert(0, danger_warning)  # Put at top
        all_cons.append(f"Passes through dangerous conditions ({dangerous_waypoints} waypoints)")
    
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

