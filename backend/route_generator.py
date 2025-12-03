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

