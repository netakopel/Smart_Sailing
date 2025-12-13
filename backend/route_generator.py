"""
Route Generator - Creates 3 route options between start and end points

This module handles all the geographic calculations:
- Distance between points (Haversine formula)
- Bearing/direction between points  
- Generating waypoints along direct and curved paths
"""

import math
from datetime import datetime, timedelta
from typing import List
from models import Coordinates, Waypoint, RouteRequest, BoatType, BOAT_PROFILES, RouteType
from dataclasses import dataclass


# Earth's radius in nautical miles
EARTH_RADIUS_NM = 3440.065


def to_radians(degrees: float) -> float:
    """Convert degrees to radians"""
    return degrees * (math.pi / 180)


def to_degrees(radians: float) -> float:
    """Convert radians to degrees"""
    return radians * (180 / math.pi)


def calculate_distance(start: Coordinates, end: Coordinates) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    The Haversine formula calculates the shortest distance over the 
    Earth's surface (great-circle distance).
    
    Args:
        start: Starting coordinates
        end: Ending coordinates
        
    Returns:
        Distance in nautical miles
    """
    lat1 = to_radians(start.lat)
    lat2 = to_radians(end.lat)
    delta_lat = to_radians(end.lat - start.lat)
    delta_lng = to_radians(end.lng - start.lng)

    # Haversine formula
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1) * math.cos(lat2) * 
         math.sin(delta_lng / 2) ** 2)
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return EARTH_RADIUS_NM * c


def calculate_bearing(start: Coordinates, end: Coordinates) -> float:
    """
    Calculate the initial bearing (direction) from start to end.
    
    Args:
        start: Starting coordinates
        end: Ending coordinates
        
    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East, etc.)
    """
    lat1 = to_radians(start.lat)
    lat2 = to_radians(end.lat)
    delta_lng = to_radians(end.lng - start.lng)

    y = math.sin(delta_lng) * math.cos(lat2)
    x = (math.cos(lat1) * math.sin(lat2) - 
         math.sin(lat1) * math.cos(lat2) * math.cos(delta_lng))
    
    bearing = to_degrees(math.atan2(y, x))
    
    # Normalize to 0-360
    return (bearing + 360) % 360


def calculate_destination(start: Coordinates, distance: float, bearing: float) -> Coordinates:
    """
    Calculate the destination point given start, distance, and bearing.
    
    Args:
        start: Starting coordinates
        distance: Distance to travel in nautical miles
        bearing: Direction to travel in degrees
        
    Returns:
        Destination coordinates
    """
    lat1 = to_radians(start.lat)
    lng1 = to_radians(start.lng)
    bearing_rad = to_radians(bearing)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance / EARTH_RADIUS_NM) +
        math.cos(lat1) * math.sin(distance / EARTH_RADIUS_NM) * math.cos(bearing_rad)
    )

    lng2 = lng1 + math.atan2(
        math.sin(bearing_rad) * math.sin(distance / EARTH_RADIUS_NM) * math.cos(lat1),
        math.cos(distance / EARTH_RADIUS_NM) - math.sin(lat1) * math.sin(lat2)
    )

    return Coordinates(lat=to_degrees(lat2), lng=to_degrees(lng2))


def generate_direct_waypoints(
    start: Coordinates,
    end: Coordinates,
    num_waypoints: int,
    departure_time: datetime,
    avg_speed: float
) -> List[Waypoint]:
    """
    Generate waypoints along a direct (straight) path.
    
    Args:
        start: Starting point
        end: Ending point
        num_waypoints: Number of intermediate points (total will be num_waypoints + 1)
        departure_time: When the journey starts
        avg_speed: Average boat speed in knots
        
    Returns:
        List of waypoints with estimated arrival times
    """
    waypoints = []
    total_distance = calculate_distance(start, end)
    bearing = calculate_bearing(start, end)
    
    for i in range(num_waypoints + 1):
        fraction = i / num_waypoints
        distance_from_start = total_distance * fraction
        
        # Calculate position
        if i == 0:
            position = start
        elif i == num_waypoints:
            position = end
        else:
            position = calculate_destination(start, distance_from_start, bearing)
        
        # Calculate arrival time based on distance and speed
        hours_from_start = distance_from_start / avg_speed
        arrival_time = departure_time + timedelta(hours=hours_from_start)
        
        waypoints.append(Waypoint(
            position=position,
            estimated_arrival=arrival_time.isoformat()
        ))
    
    return waypoints


def generate_curved_waypoints(
    start: Coordinates,
    end: Coordinates,
    num_waypoints: int,
    departure_time: datetime,
    avg_speed: float,
    offset_direction: str,  # 'left' or 'right'
    offset_amount: float    # nautical miles
) -> List[Waypoint]:
    """
    Generate waypoints along a curved path (offset left or right of direct route).
    
    This creates an arc that bulges away from the direct line,
    useful for avoiding weather or finding better wind angles.
    
    Args:
        start: Starting point
        end: Ending point
        num_waypoints: Number of intermediate points
        departure_time: When the journey starts
        avg_speed: Average boat speed in knots
        offset_direction: 'left' (port) or 'right' (starboard)
        offset_amount: Maximum offset distance in nautical miles
        
    Returns:
        List of waypoints forming a curved path
    """
    waypoints = []
    total_distance = calculate_distance(start, end)
    main_bearing = calculate_bearing(start, end)
    
    # Calculate perpendicular bearing for offset
    # Left (port) = -90 degrees from travel direction
    # Right (starboard) = +90 degrees from travel direction
    if offset_direction == 'left':
        perp_bearing = (main_bearing - 90 + 360) % 360
    else:
        perp_bearing = (main_bearing + 90) % 360
    
    cumulative_distance = 0.0
    prev_position = None
    
    for i in range(num_waypoints + 1):
        fraction = i / num_waypoints
        
        # Create a sine curve for smooth offset (maximum at middle of route)
        offset_factor = math.sin(fraction * math.pi)
        current_offset = offset_amount * offset_factor
        
        # Get position
        if i == 0:
            position = start
        elif i == num_waypoints:
            position = end
        else:
            # First, find point on direct line
            distance_from_start = total_distance * fraction
            direct_point = calculate_destination(start, distance_from_start, main_bearing)
            # Then offset it perpendicular to the route
            position = calculate_destination(direct_point, current_offset, perp_bearing)
        
        # Calculate cumulative distance (for accurate time estimates)
        if prev_position is not None:
            cumulative_distance += calculate_distance(prev_position, position)
        
        hours_from_start = cumulative_distance / avg_speed
        arrival_time = departure_time + timedelta(hours=hours_from_start)
        
        waypoints.append(Waypoint(
            position=position,
            estimated_arrival=arrival_time.isoformat()
        ))
        
        prev_position = position
    
    return waypoints


def calculate_route_distance(waypoints: List[Waypoint]) -> float:
    """Calculate total distance of a route by summing segment distances."""
    total = 0.0
    for i in range(1, len(waypoints)):
        total += calculate_distance(
            waypoints[i - 1].position, 
            waypoints[i].position
        )
    return total


def format_duration(hours: float) -> str:
    """Convert hours to human-readable format like '12h 30m'"""
    if hours < 1:
        return f"{int(hours * 60)} minutes"
    
    h = int(hours)
    m = int((hours - h) * 60)
    
    if m == 0:
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{h}h {m}m"


@dataclass
@dataclass
class GeneratedRoute:
    """Intermediate route data before weather/scoring is added"""
    name: str
    route_type: RouteType
    waypoints: List[Waypoint]
    distance: float
    estimated_hours: float
    estimated_time: str


def generate_routes(request: RouteRequest) -> List[GeneratedRoute]:
    """
    Main function: Generate 3 route options.
    
    Creates:
    1. Direct Route - shortest path
    2. Northern Route - curves north (may have different weather)
    3. Southern Route - curves south (may have different weather)
    
    Args:
        request: User's route request with start, end, boat type, and departure
        
    Returns:
        List of 3 generated routes (without weather data yet)
    """
    start = request.start
    end = request.end
    boat = BOAT_PROFILES[request.boat_type]
    departure = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
    num_waypoints = 5  # Creates 6 total points including start/end
    
    direct_distance = calculate_distance(start, end)
    
    # Offset scales with distance (5% of distance, min 10nm, max 50nm)
    offset_amount = min(50, max(10, direct_distance * 0.05))
    
    routes = []
    
    # 1. Direct Route
    direct_waypoints = generate_direct_waypoints(
        start, end, num_waypoints, departure, boat.avg_speed
    )
    direct_route_distance = calculate_route_distance(direct_waypoints)
    direct_hours = direct_route_distance / boat.avg_speed
    
    routes.append(GeneratedRoute(
        name="Direct Route",
        route_type=RouteType.DIRECT,
        waypoints=direct_waypoints,
        distance=round(direct_route_distance, 1),
        estimated_hours=direct_hours,
        estimated_time=format_duration(direct_hours)
    ))
    
    # 2. Port Route (curves left of direct route)
    port_waypoints = generate_curved_waypoints(
        start, end, num_waypoints, departure, boat.avg_speed, 'left', offset_amount
    )
    port_distance = calculate_route_distance(port_waypoints)
    port_hours = port_distance / boat.avg_speed
    
    routes.append(GeneratedRoute(
        name="Port Route",
        route_type=RouteType.PORT,
        waypoints=port_waypoints,
        distance=round(port_distance, 1),
        estimated_hours=port_hours,
        estimated_time=format_duration(port_hours)
    ))
    
    # 3. Starboard Route (curves right of direct route)
    starboard_waypoints = generate_curved_waypoints(
        start, end, num_waypoints, departure, boat.avg_speed, 'right', offset_amount
    )
    starboard_distance = calculate_route_distance(starboard_waypoints)
    starboard_hours = starboard_distance / boat.avg_speed
    
    routes.append(GeneratedRoute(
        name="Starboard Route",
        route_type=RouteType.STARBOARD,
        waypoints=starboard_waypoints,
        distance=round(starboard_distance, 1),
        estimated_hours=starboard_hours,
        estimated_time=format_duration(starboard_hours)
    ))
    
    return routes


def recalculate_route_times_with_wind(
    route: GeneratedRoute,
    boat_type: BoatType,
    departure_time: datetime
) -> GeneratedRoute:
    """
    Recalculate route estimated times based on actual wind conditions at waypoints.
    
    This function should be called AFTER weather data has been fetched for waypoints.
    It calculates realistic boat speeds considering wind angles, including penalties
    for no-go zones where sailing directly into the wind is impossible/very slow.
    
    Args:
        route: Route with waypoints that have weather data
        boat_type: Type of boat
        departure_time: Departure time
        
    Returns:
        Updated route with recalculated times and total estimated_hours
    """
    from polars import get_boat_speed, calculate_wind_angle
    
    if not route.waypoints or len(route.waypoints) < 2:
        return route
    
    boat = BOAT_PROFILES[boat_type]
    updated_waypoints = []
    current_time = departure_time
    
    for i, waypoint in enumerate(route.waypoints):
        if i == 0:
            # First waypoint - use departure time
            updated_waypoints.append(Waypoint(
                position=waypoint.position,
                estimated_arrival=current_time.isoformat(),
                weather=waypoint.weather
            ))
            continue
        
        # Calculate segment from previous waypoint to current
        prev_waypoint = route.waypoints[i - 1]
        segment_distance = calculate_distance(prev_waypoint.position, waypoint.position)
        heading = calculate_bearing(prev_waypoint.position, waypoint.position)
        
        # Get wind conditions at previous waypoint (where we start this segment)
        if prev_waypoint.weather:
            wind_speed = prev_waypoint.weather.wind_speed
            wind_direction = prev_waypoint.weather.wind_direction
            
            # Calculate wind angle relative to our heading
            wind_angle = calculate_wind_angle(heading, wind_direction)
            
            # Get actual boat speed from polars (accounts for wind angle, including no-go zones)
            boat_speed = get_boat_speed(wind_speed, wind_angle, boat_type.value)
            
            # If in no-go zone (speed = 0) or very slow, use a minimum penalty speed
            # This represents very slow progress (motoring, or extreme tacking)
            if boat_speed < 1.0:
                boat_speed = boat.avg_speed * 0.2  # 20% of average speed as penalty
        else:
            # No weather data, use average speed
            boat_speed = boat.avg_speed
        
        # Calculate time for this segment
        if boat_speed > 0:
            segment_hours = segment_distance / boat_speed
        else:
            # Fallback: use average speed
            segment_hours = segment_distance / boat.avg_speed
        
        current_time = current_time + timedelta(hours=segment_hours)
        
        updated_waypoints.append(Waypoint(
            position=waypoint.position,
            estimated_arrival=current_time.isoformat(),
            weather=waypoint.weather
        ))
    
    # Calculate total time
    total_time_hours = (current_time - departure_time).total_seconds() / 3600
    
    # Return updated route
    return GeneratedRoute(
        name=route.name,
        route_type=route.route_type,
        waypoints=updated_waypoints,
        distance=route.distance,  # Distance doesn't change
        estimated_hours=total_time_hours,
        estimated_time=format_duration(total_time_hours)
    )
