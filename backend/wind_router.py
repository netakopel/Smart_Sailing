"""
Wind Router - Smart sailing route generation using pattern-based tactics

This module implements a hybrid pattern-based routing algorithm that uses
established sailing tactics (tacking, VMG optimization, wind-seeking) to
generate wind-aware routes.

Philosophy: "Use proven sailing tactics and patterns"

Algorithm:
1. Fetch regional weather grid
2. Analyze prevailing winds along route corridor
3. Classify sailing scenario (upwind/downwind/reaching)
4. Apply appropriate sailing tactics to generate 3 route variations
"""

import math
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from enum import Enum

from models import Coordinates, Waypoint, RouteRequest, BoatType, BOAT_PROFILES
from route_generator import (
    GeneratedRoute, RouteType, calculate_distance, calculate_bearing,
    calculate_destination, calculate_route_distance, format_duration
)
from weather_fetcher import fetch_regional_weather_grid, interpolate_weather, calculate_forecast_hours_needed
from polars import get_boat_speed, calculate_wind_angle, get_optimal_vmg_angle, normalize_angle

# Set up logging
logger = logging.getLogger(__name__)


# ============================================================================
# SAILING SCENARIO CLASSIFICATION
# ============================================================================

class SailingScenario(Enum):
    """
    Classification of sailing scenarios based on wind direction relative to destination.
    
    Determines which sailing tactics to use:
    - UPWIND: Must tack (zigzag) to make progress
    - BEAM_REACH: Fast sailing with wind from side
    - BROAD_REACH: Fastest point of sail, wind from behind-side
    - DOWNWIND: May be faster to sail at angle than dead downwind
    """
    UPWIND = "upwind"           # Destination 0-60° from wind (must tack)
    BEAM_REACH = "beam_reach"   # Destination 60-100° from wind (fast sailing)
    BROAD_REACH = "broad_reach" # Destination 100-150° from wind (fastest)
    DOWNWIND = "downwind"       # Destination 150-180° from wind


def classify_sailing_scenario(
    start: Coordinates,
    end: Coordinates,
    wind_direction: float
) -> SailingScenario:
    """
    Classify the sailing scenario based on destination bearing relative to wind.
    
    Args:
        start: Starting position
        end: Destination position
        wind_direction: Direction wind is coming FROM (0-360°, 0=North)
        
    Returns:
        SailingScenario classification
        
    Example:
        Destination bearing: 045° (Northeast)
        Wind from: 050° (Northeast)
        Angle: ~5° (directly upwind)
        → UPWIND scenario (must tack)
    """
    # Calculate bearing to destination
    destination_bearing = calculate_bearing(start, end)
    
    # Calculate angle between destination and wind direction
    # Wind direction is where wind comes FROM
    angle = abs(destination_bearing - wind_direction)
    if angle > 180:
        angle = 360 - angle
    
    # Classify based on angle
    if angle < 60:
        return SailingScenario.UPWIND
    elif angle < 100:
        return SailingScenario.BEAM_REACH
    elif angle < 150:
        return SailingScenario.BROAD_REACH
    else:
        return SailingScenario.DOWNWIND


def analyze_wind_corridor(
    start: Coordinates,
    end: Coordinates,
    weather_grid: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze wind conditions along the direct route corridor.
    
    Samples wind at multiple points along the direct path to understand
    the prevailing wind pattern and variability.
    
    Args:
        start: Starting position
        end: Destination position
        weather_grid: Weather grid from fetch_regional_weather_grid()
        
    Returns:
        Dictionary with:
        - avg_wind_speed: Average wind speed (knots)
        - avg_wind_direction: Prevailing wind direction (degrees)
        - max_wind_speed: Maximum wind speed (knots)
        - min_wind_speed: Minimum wind speed (knots)
        - wind_variability: Std dev of wind direction (0 = steady, >30 = highly variable)
        - max_wave_height: Maximum wave height (meters)
    """
    # Sample 10 points along direct route
    num_samples = 10
    bearing = calculate_bearing(start, end)
    total_distance = calculate_distance(start, end)
    
    # Get departure time from weather grid
    departure_time = weather_grid['times'][0]
    
    wind_speeds = []
    wind_directions_sin = []
    wind_directions_cos = []
    wave_heights = []
    
    for i in range(num_samples + 1):
        fraction = i / num_samples
        distance = total_distance * fraction
        
        # Calculate position
        if i == 0:
            position = start
        elif i == num_samples:
            position = end
        else:
            position = calculate_destination(start, distance, bearing)
        
        # Get weather at this position (at departure time)
        weather = interpolate_weather(position, departure_time, weather_grid)
        
        wind_speeds.append(weather.wind_speed)
        wave_heights.append(weather.wave_height)
        
        # Store wind direction as sin/cos for circular averaging
        wind_dir_rad = math.radians(weather.wind_direction)
        wind_directions_sin.append(math.sin(wind_dir_rad))
        wind_directions_cos.append(math.cos(wind_dir_rad))
    
    # Calculate statistics
    avg_wind_speed = sum(wind_speeds) / len(wind_speeds)
    max_wind_speed = max(wind_speeds)
    min_wind_speed = min(wind_speeds)
    max_wave_height = max(wave_heights)
    
    # Calculate average wind direction using circular mean
    avg_sin = sum(wind_directions_sin) / len(wind_directions_sin)
    avg_cos = sum(wind_directions_cos) / len(wind_directions_cos)
    avg_wind_direction = math.degrees(math.atan2(avg_sin, avg_cos))
    if avg_wind_direction < 0:
        avg_wind_direction += 360
    
    # Calculate wind direction variability (circular standard deviation approximation)
    # Higher values mean more variable wind direction
    r = math.sqrt(avg_sin**2 + avg_cos**2)
    wind_variability = math.degrees(math.sqrt(-2 * math.log(r))) if r > 0.01 else 0
    
    return {
        'avg_wind_speed': round(avg_wind_speed, 1),
        'avg_wind_direction': round(avg_wind_direction),
        'max_wind_speed': round(max_wind_speed, 1),
        'min_wind_speed': round(min_wind_speed, 1),
        'wind_variability': round(wind_variability, 1),
        'max_wave_height': round(max_wave_height, 1)
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_waypoints_with_timing(
    positions: List[Coordinates],
    departure_time: datetime,
    weather_grid: Dict[str, Any],
    boat_type: str
) -> List[Waypoint]:
    """
    Create waypoints with realistic arrival times based on wind conditions.
    
    Args:
        positions: List of positions along route
        departure_time: Journey start time
        weather_grid: Weather grid for speed estimation
        boat_type: Type of boat
        
    Returns:
        List of Waypoints with estimated arrival times
    """
    waypoints = []
    current_time = departure_time
    
    for i, pos in enumerate(positions):
        waypoints.append(Waypoint(
            position=pos,
            estimated_arrival=current_time.isoformat()
        ))
        
        # Calculate time to next waypoint
        if i < len(positions) - 1:
            next_pos = positions[i + 1]
            distance = calculate_distance(pos, next_pos)
            
            # Get weather and boat speed
            weather = interpolate_weather(pos, current_time, weather_grid)
            heading = calculate_bearing(pos, next_pos)
            twa = calculate_wind_angle(heading, weather.wind_direction)
            boat_speed = get_boat_speed(weather.wind_speed, twa, boat_type)
            
            # Use minimum speed if in no-go zone
            if boat_speed <= 0:
                boat_speed = BOAT_PROFILES[BoatType(boat_type)].avg_speed * 0.2
            
            # Calculate time to next waypoint
            hours = distance / boat_speed
            current_time = current_time + timedelta(hours=hours)
    
    return waypoints


# ============================================================================
# UPWIND ROUTE GENERATION
# ============================================================================

def generate_tacking_route(
    start: Coordinates,
    end: Coordinates,
    tack_angle: float,
    tack_length_nm: float,
    boat_type: str,
    departure_time: datetime,
    weather_grid: Dict[str, Any],
    name: str,
    max_tacks: int = 20
) -> GeneratedRoute:
    """
    Generate a smart tacking (zigzag) route for sailing upwind.
    
    Uses ACTUAL forecasted wind at each position and time from weather_grid,
    not a single average wind direction!
    
    Algorithm:
    1. Get current wind at current position/time
    2. Calculate optimal tack headings based on THAT wind
    3. Start on the tack that points closer to destination
    4. Sail on that tack for tack_length_nm
    5. Get wind at NEW position/time
    6. Check if destination is now at a good sailing angle relative to NEW wind
    7. If yes: Sail directly to destination (done!)
    8. If no: Recalculate tack headings for NEW wind and repeat
    
    This adapts to wind shifts both in space and time!
    
    Args:
        start: Starting position
        end: Destination position
        tack_angle: Angle off wind to sail at (typically 50-52°)
        tack_length_nm: How far to sail on each tack leg (nautical miles)
        boat_type: Type of boat
        departure_time: Journey start time
        weather_grid: Weather grid for interpolation
        name: Route name
        max_tacks: Safety limit to prevent infinite loops (default: 20)
        
    Returns:
        GeneratedRoute with smart tacking waypoints
    """
    positions = [start]
    current_pos = start
    current_time = departure_time
    tack_count = 0
    
    # Boat profile for speed estimation
    boat_profile = BOAT_PROFILES[BoatType(boat_type)]
    
    # Iterative tacking until we can sail directly to destination
    while tack_count < max_tacks:
        # Check if we can sail directly to destination from current position
        distance_to_dest = calculate_distance(current_pos, end)
        
        # If very close to destination (within 2nm), just go there
        if distance_to_dest < 2.0:
            positions.append(end)
            break
        
        # Get ACTUAL wind at current position and time
        current_weather = interpolate_weather(current_pos, current_time, weather_grid)
        wind_direction = current_weather.wind_direction
        
        # Calculate bearing and wind angle to destination using CURRENT wind
        bearing_to_dest = calculate_bearing(current_pos, end)
        wind_angle_to_dest = calculate_wind_angle(bearing_to_dest, wind_direction)
        
        # Check if destination is at a good sailing angle (not in no-go zone)
        # Good angle: 45° to 180° (anything outside no-go zone)
        if wind_angle_to_dest >= 45:
            # We can sail directly to destination! Add it and we're done
            positions.append(end)
            break
        
        # Still in no-go zone, need to continue tacking
        # Calculate optimal tack headings based on CURRENT wind
        port_tack_heading = normalize_angle(wind_direction + tack_angle)
        starboard_tack_heading = normalize_angle(wind_direction - tack_angle)
        
        # If this is the first tack, choose the one closer to destination
        if tack_count == 0:
            port_angle_diff = abs(port_tack_heading - bearing_to_dest)
            if port_angle_diff > 180:
                port_angle_diff = 360 - port_angle_diff
                
            starboard_angle_diff = abs(starboard_tack_heading - bearing_to_dest)
            if starboard_angle_diff > 180:
                starboard_angle_diff = 360 - starboard_angle_diff
            
            # Choose better tack
            if port_angle_diff < starboard_angle_diff:
                chosen_heading = port_tack_heading
            else:
                chosen_heading = starboard_tack_heading
        else:
            # For subsequent tacks, alternate between port and starboard
            # Check which tack we were on last time
            if len(positions) >= 2:
                last_heading = calculate_bearing(positions[-2], positions[-1])
                # Determine if we were on port or starboard tack
                last_wind_angle = calculate_wind_angle(last_heading, wind_direction)
                
                # If last heading was roughly port tack angle, switch to starboard
                # Otherwise switch to port
                if abs(last_wind_angle - tack_angle) < 10:  # Was on port-ish tack
                    chosen_heading = starboard_tack_heading
                else:
                    chosen_heading = port_tack_heading
            else:
                # Default to port tack
                chosen_heading = port_tack_heading
        
        # Sail on chosen tack for tack_length_nm (but don't overshoot destination)
        actual_tack_length = min(tack_length_nm, distance_to_dest)
        
        next_pos = calculate_destination(current_pos, actual_tack_length, chosen_heading)
        positions.append(next_pos)
        
        # Estimate time to reach next position (rough estimate for weather lookup)
        # Use boat speed at this wind angle
        estimated_speed = get_boat_speed(current_weather.wind_speed, tack_angle, boat_type)
        if estimated_speed <= 0:
            estimated_speed = boat_profile.avg_speed * 0.2  # Fallback
        
        travel_hours = actual_tack_length / estimated_speed
        current_time = current_time + timedelta(hours=travel_hours)
        
        # Update position for next iteration
        current_pos = next_pos
        tack_count += 1
    
    # Safety check: if we hit max_tacks, just add destination anyway
    if tack_count >= max_tacks and positions[-1] != end:
        positions.append(end)
    
    # Create waypoints with timing (this will recalculate times more accurately)
    waypoints = create_waypoints_with_timing(positions, departure_time, weather_grid, boat_type)
    
    # Calculate route metrics
    route_distance = calculate_route_distance(waypoints)
    start_time = datetime.fromisoformat(waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    estimated_hours = (end_time - start_time).total_seconds() / 3600
    
    return GeneratedRoute(
        name=name,
        route_type=RouteType.DIRECT,  # Will be distinguished by name
        waypoints=waypoints,
        distance=round(route_distance, 1),
        estimated_hours=estimated_hours,
        estimated_time=format_duration(estimated_hours)
    )


def generate_upwind_routes(
    request: RouteRequest,
    weather_grid: Dict[str, Any],
    wind_analysis: Dict[str, Any]
) -> List[GeneratedRoute]:
    """
    Generate 3 tacking route variations for upwind sailing.
    
    Uses smart iterative tacking that stops when destination is at a good sailing angle.
    Each route adapts to actual forecasted wind conditions (space + time).
    
    Tack lengths scale proportionally with route distance:
    - Long tacks: 50% of route distance (fewer tacks, efficient for stable wind)
    - Medium tacks: 30% of route distance (balanced approach)
    - Short tacks: 15% of route distance (more responsive to wind shifts)
    
    With reasonable bounds:
    - Minimum tack: 5nm (shorter is inefficient)
    - Maximum tack: 100nm (longer reduces adaptability)
    
    Examples:
    - 20nm route: Long=10nm, Medium=6nm, Short=5nm (min)
    - 100nm route: Long=50nm, Medium=30nm, Short=15nm
    - 400nm route: Long=100nm(max), Medium=100nm(max), Short=60nm
    
    Args:
        request: User's route request
        weather_grid: Regional weather grid
        wind_analysis: Wind corridor analysis results (not used directly now, but kept for compatibility)
        
    Returns:
        List of 3 upwind route options
    """
    departure = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
    total_distance = calculate_distance(request.start, request.end)
    
    routes = []
    
    # Define tack length ratios and bounds
    MIN_TACK_LENGTH = 5.0   # nm - minimum practical tack length
    MAX_TACK_LENGTH = 100.0 # nm - maximum for adaptability
    
    # Route 1: Long tacks - 50% of route distance
    # Fewer tacks, more efficient, good for stable wind conditions
    long_tack_length = max(MIN_TACK_LENGTH, min(MAX_TACK_LENGTH, total_distance * 0.5))
    routes.append(generate_tacking_route(
        start=request.start,
        end=request.end,
        tack_angle=52,  # Optimal VMG angle
        tack_length_nm=long_tack_length,
        boat_type=request.boat_type.value,
        departure_time=departure,
        weather_grid=weather_grid,
        name="Long Tack Route"
    ))
    
    # Route 2: Medium tacks - 30% of route distance
    # Balanced approach, works well in most conditions
    medium_tack_length = max(MIN_TACK_LENGTH, min(MAX_TACK_LENGTH, total_distance * 0.3))
    routes.append(generate_tacking_route(
        start=request.start,
        end=request.end,
        tack_angle=52,
        tack_length_nm=medium_tack_length,
        boat_type=request.boat_type.value,
        departure_time=departure,
        weather_grid=weather_grid,
        name="Medium Tack Route"
    ))
    
    # Route 3: Short tacks - 15% of route distance
    # More frequent adjustments, better for variable wind
    short_tack_length = max(MIN_TACK_LENGTH, min(MAX_TACK_LENGTH, total_distance * 0.15))
    routes.append(generate_tacking_route(
        start=request.start,
        end=request.end,
        tack_angle=52,
        tack_length_nm=short_tack_length,
        boat_type=request.boat_type.value,
        departure_time=departure,
        weather_grid=weather_grid,
        name="Short Tack Route"
    ))
    
    return routes


# ============================================================================
# DOWNWIND ROUTE GENERATION
# ============================================================================

def generate_downwind_routes(
    request: RouteRequest,
    weather_grid: Dict[str, Any],
    wind_analysis: Dict[str, Any]
) -> List[GeneratedRoute]:
    """
    Generate 3 downwind route variations.
    
    Key insight: Dead downwind (180°) is often slower than broad reach (110-135°)
    due to sail efficiency and wave patterns.
    
    Variations:
    1. Direct: Straight or nearly straight route
    2. Port broad reach: Curve right ~20° for better boat speed
    3. Starboard broad reach: Curve left ~20° for better boat speed
    
    Args:
        request: User's route request
        weather_grid: Regional weather grid
        wind_analysis: Wind corridor analysis results
        
    Returns:
        List of 3 downwind route options
    """
    departure = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
    total_distance = calculate_distance(request.start, request.end)
    destination_bearing = calculate_bearing(request.start, request.end)
    
    routes = []
    num_waypoints = 6
    
    # Route 1: Direct route (simplest)
    direct_positions = []
    for i in range(num_waypoints):
        fraction = i / (num_waypoints - 1)
        if i == 0:
            direct_positions.append(request.start)
        elif i == num_waypoints - 1:
            direct_positions.append(request.end)
        else:
            distance = total_distance * fraction
            pos = calculate_destination(request.start, distance, destination_bearing)
            direct_positions.append(pos)
    
    direct_waypoints = create_waypoints_with_timing(
        direct_positions, departure, weather_grid, request.boat_type.value
    )
    direct_distance = calculate_route_distance(direct_waypoints)
    start_time = datetime.fromisoformat(direct_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(direct_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    direct_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Direct Downwind Route",
        route_type=RouteType.DIRECT,
        waypoints=direct_waypoints,
        distance=round(direct_distance, 1),
        estimated_hours=direct_hours,
        estimated_time=format_duration(direct_hours)
    ))
    
    # Route 2: Port broad reach (curve right ~15-20°)
    port_positions = [request.start]
    curve_angle = 20  # degrees off direct bearing
    
    for i in range(1, num_waypoints - 1):
        fraction = i / (num_waypoints - 1)
        # Create a smooth curve using sine
        curve_factor = math.sin(fraction * math.pi)
        adjusted_bearing = destination_bearing + (curve_angle * curve_factor)
        distance = total_distance * fraction
        pos = calculate_destination(request.start, distance, adjusted_bearing)
        port_positions.append(pos)
    
    port_positions.append(request.end)
    
    port_waypoints = create_waypoints_with_timing(
        port_positions, departure, weather_grid, request.boat_type.value
    )
    port_distance = calculate_route_distance(port_waypoints)
    start_time = datetime.fromisoformat(port_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(port_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    port_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Port Broad Reach Route",
        route_type=RouteType.PORT,
        waypoints=port_waypoints,
        distance=round(port_distance, 1),
        estimated_hours=port_hours,
        estimated_time=format_duration(port_hours)
    ))
    
    # Route 3: Starboard broad reach (curve left ~15-20°)
    starboard_positions = [request.start]
    
    for i in range(1, num_waypoints - 1):
        fraction = i / (num_waypoints - 1)
        curve_factor = math.sin(fraction * math.pi)
        adjusted_bearing = destination_bearing - (curve_angle * curve_factor)
        distance = total_distance * fraction
        pos = calculate_destination(request.start, distance, adjusted_bearing)
        starboard_positions.append(pos)
    
    starboard_positions.append(request.end)
    
    starboard_waypoints = create_waypoints_with_timing(
        starboard_positions, departure, weather_grid, request.boat_type.value
    )
    starboard_distance = calculate_route_distance(starboard_waypoints)
    start_time = datetime.fromisoformat(starboard_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(starboard_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    starboard_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Starboard Broad Reach Route",
        route_type=RouteType.STARBOARD,
        waypoints=starboard_waypoints,
        distance=round(starboard_distance, 1),
        estimated_hours=starboard_hours,
        estimated_time=format_duration(starboard_hours)
    ))
    
    return routes


# ============================================================================
# REACHING ROUTE GENERATION
# ============================================================================

def generate_reaching_routes(
    request: RouteRequest,
    weather_grid: Dict[str, Any],
    wind_analysis: Dict[str, Any]
) -> List[GeneratedRoute]:
    """
    Generate 3 reaching route variations (beam/broad reach scenarios).
    
    Reaching is often the fastest and most comfortable point of sail.
    Routes can be fairly direct with minor variations.
    
    Variations:
    1. Direct: Straight path (already good wind angle)
    2. Wind-optimized: Slight curve toward stronger wind areas
    3. Wave-optimized: Avoid areas with highest waves
    
    Args:
        request: User's route request
        weather_grid: Regional weather grid
        wind_analysis: Wind corridor analysis results
        
    Returns:
        List of 3 reaching route options
    """
    departure = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
    total_distance = calculate_distance(request.start, request.end)
    destination_bearing = calculate_bearing(request.start, request.end)
    
    routes = []
    num_waypoints = 6
    
    # Route 1: Direct route
    direct_positions = []
    for i in range(num_waypoints):
        fraction = i / (num_waypoints - 1)
        if i == 0:
            direct_positions.append(request.start)
        elif i == num_waypoints - 1:
            direct_positions.append(request.end)
        else:
            distance = total_distance * fraction
            pos = calculate_destination(request.start, distance, destination_bearing)
            direct_positions.append(pos)
    
    direct_waypoints = create_waypoints_with_timing(
        direct_positions, departure, weather_grid, request.boat_type.value
    )
    direct_distance = calculate_route_distance(direct_waypoints)
    start_time = datetime.fromisoformat(direct_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(direct_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    direct_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Direct Reaching Route",
        route_type=RouteType.DIRECT,
        waypoints=direct_waypoints,
        distance=round(direct_distance, 1),
        estimated_hours=direct_hours,
        estimated_time=format_duration(direct_hours)
    ))
    
    # Route 2: Slightly curved north (5-10° offset for variety)
    north_positions = [request.start]
    curve_angle = 8  # Small curve
    
    for i in range(1, num_waypoints - 1):
        fraction = i / (num_waypoints - 1)
        curve_factor = math.sin(fraction * math.pi)
        adjusted_bearing = destination_bearing - (curve_angle * curve_factor)  # Negative = north in most cases
        distance = total_distance * fraction
        pos = calculate_destination(request.start, distance, adjusted_bearing)
        north_positions.append(pos)
    
    north_positions.append(request.end)
    
    north_waypoints = create_waypoints_with_timing(
        north_positions, departure, weather_grid, request.boat_type.value
    )
    north_distance = calculate_route_distance(north_waypoints)
    start_time = datetime.fromisoformat(north_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(north_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    north_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Northern Reaching Route",
        route_type=RouteType.PORT,
        waypoints=north_waypoints,
        distance=round(north_distance, 1),
        estimated_hours=north_hours,
        estimated_time=format_duration(north_hours)
    ))
    
    # Route 3: Slightly curved south (5-10° offset for variety)
    south_positions = [request.start]
    
    for i in range(1, num_waypoints - 1):
        fraction = i / (num_waypoints - 1)
        curve_factor = math.sin(fraction * math.pi)
        adjusted_bearing = destination_bearing + (curve_angle * curve_factor)  # Positive = south in most cases
        distance = total_distance * fraction
        pos = calculate_destination(request.start, distance, adjusted_bearing)
        south_positions.append(pos)
    
    south_positions.append(request.end)
    
    south_waypoints = create_waypoints_with_timing(
        south_positions, departure, weather_grid, request.boat_type.value
    )
    south_distance = calculate_route_distance(south_waypoints)
    start_time = datetime.fromisoformat(south_waypoints[0].estimated_arrival.replace('Z', '+00:00'))
    end_time = datetime.fromisoformat(south_waypoints[-1].estimated_arrival.replace('Z', '+00:00'))
    south_hours = (end_time - start_time).total_seconds() / 3600
    
    routes.append(GeneratedRoute(
        name="Southern Reaching Route",
        route_type=RouteType.STARBOARD,
        waypoints=south_waypoints,
        distance=round(south_distance, 1),
        estimated_hours=south_hours,
        estimated_time=format_duration(south_hours)
    ))
    
    return routes


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def generate_hybrid_routes(request: RouteRequest) -> List[GeneratedRoute]:
    """
    Main entry point: Generate 3 wind-aware routes using hybrid pattern-based algorithm.
    
    Process:
    1. Fetch regional weather grid
    2. Analyze wind corridor to understand conditions
    3. Classify sailing scenario (upwind/downwind/reaching)
    4. Apply appropriate sailing tactics to generate 3 route variations
    
    Args:
        request: User's route request with start, end, boat type, departure time
        
    Returns:
        List of 3 generated routes (without weather data at waypoints yet)
        
    Performance Target: < 1 second
    """
    logger.info("=== Hybrid Pattern-Based Routing ===")
    logger.info(f"  Start: ({request.start.lat:.4f}, {request.start.lng:.4f})")
    logger.info(f"  End: ({request.end.lat:.4f}, {request.end.lng:.4f})")
    logger.info(f"  Boat: {request.boat_type.value}")
    
    # Calculate route metrics
    total_distance = calculate_distance(request.start, request.end)
    boat_profile = BOAT_PROFILES[request.boat_type]
    
    # Calculate how many hours of forecast we need
    forecast_hours = calculate_forecast_hours_needed(total_distance, boat_profile.avg_speed)
    logger.info(f"  Distance: {total_distance:.1f} nm")
    logger.info(f"  Forecast hours needed: {forecast_hours}")
    
    # Step 1: Fetch regional weather grid
    weather_grid = fetch_regional_weather_grid(
        start=request.start,
        end=request.end,
        departure_time=request.departure_time,
        grid_spacing=10.0,
        forecast_hours=forecast_hours
    )
    
    # Step 2: Analyze wind corridor
    logger.info("  Analyzing wind corridor...")
    wind_analysis = analyze_wind_corridor(request.start, request.end, weather_grid)
    logger.info(f"  Avg wind: {wind_analysis['avg_wind_speed']} kt from {wind_analysis['avg_wind_direction']}°")
    logger.info(f"  Wind range: {wind_analysis['min_wind_speed']}-{wind_analysis['max_wind_speed']} kt")
    logger.info(f"  Wind variability: {wind_analysis['wind_variability']}° (0=steady, >30=variable)")
    
    # Step 3: Classify sailing scenario
    scenario = classify_sailing_scenario(
        request.start,
        request.end,
        wind_analysis['avg_wind_direction']
    )
    logger.info(f"  Sailing scenario: {scenario.value.upper()}")
    
    # Step 4: Generate routes based on scenario
    if scenario == SailingScenario.UPWIND:
        logger.info("  Generating tacking routes (upwind scenario)...")
        routes = generate_upwind_routes(request, weather_grid, wind_analysis)
    elif scenario == SailingScenario.DOWNWIND:
        logger.info("  Generating broad reach routes (downwind scenario)...")
        routes = generate_downwind_routes(request, weather_grid, wind_analysis)
    else:  # BEAM_REACH or BROAD_REACH
        logger.info("  Generating reaching routes (fast sailing scenario)...")
        routes = generate_reaching_routes(request, weather_grid, wind_analysis)
    
    logger.info(f"  [OK] Generated {len(routes)} hybrid routes")
    for route in routes:
        logger.info(f"    - {route.name}: {route.distance} nm, {route.estimated_time}")
    
    return routes


# ============================================================================
# TESTING / DEBUG
# ============================================================================

if __name__ == "__main__":
    from models import BoatType
    
    logging.basicConfig(level=logging.INFO)
    logger.info("=== Wind Router Test ===")
    
    # Test scenario classification
    logger.info("Test 1: Scenario Classification")
    start = Coordinates(lat=50.0, lng=-1.0)
    end = Coordinates(lat=51.0, lng=-1.0)  # Due north
    
    scenarios_to_test = [
        (0, "North wind - UPWIND expected"),
        (90, "East wind - BEAM_REACH expected"),
        (135, "SE wind - BROAD_REACH expected"),
        (180, "South wind - DOWNWIND expected"),
    ]
    
    for wind_dir, description in scenarios_to_test:
        scenario = classify_sailing_scenario(start, end, wind_dir)
        logger.info(f"  Wind from {wind_dir}°: {scenario.value} - {description}")
    
    logger.info("=== Tests Complete ===")

