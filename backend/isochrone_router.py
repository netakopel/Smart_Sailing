"""
Isochrone Weather Router - Optimal sailing route using time-based propagation

This module implements the isochrone method for sailing route optimization.
An isochrone is a curve connecting all points reachable in the same time.

Algorithm Overview:
1. Start at origin at t=0
2. For each time step:
   - From all currently reachable points
   - Try sailing in multiple directions
   - Calculate where you can reach in the next time interval
   - Keep track of the fastest way to reach each location
3. Continue until destination is reached
4. Trace back optimal path from destination to start

Key Features:
- Naturally handles time-varying weather (uses forecast at arrival time)
- Automatically avoids no-go zones (boat speed = 0)
- Guaranteed to find optimal route (within discretization limits)
- Optimizations: pruning, adaptive time steps, directional focusing

Based on algorithms used in professional sailing software (OpenCPN, Expedition, qtVlm)
"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

from models import Coordinates, Waypoint, RouteRequest, BoatType, WaypointWeather
from route_generator import (
    calculate_distance, calculate_bearing, calculate_destination,
    calculate_route_distance, format_duration, GeneratedRoute, RouteType
)
from weather_fetcher import fetch_regional_weather_grid, interpolate_weather, calculate_forecast_hours_needed
from polars import get_boat_speed, calculate_wind_angle, normalize_angle


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class IsochronePoint:
    """
    A point in space-time representing a reachable position at a specific time.
    
    Attributes:
        position: Lat/lng coordinates
        time_hours: Time elapsed from start (hours)
        parent: Previous point in optimal path (for reconstruction)
        heading: Heading used to reach this point from parent (degrees)
        accumulated_distance: Total distance sailed to reach this point (nm)
    """
    position: Coordinates
    time_hours: float
    parent: Optional['IsochronePoint'] = None
    heading: Optional[float] = None
    accumulated_distance: float = 0.0
    
    def __hash__(self):
        # For use in sets
        return hash((round(self.position.lat, 4), round(self.position.lng, 4)))
    
    def __eq__(self, other):
        if not isinstance(other, IsochronePoint):
            return False
        return (round(self.position.lat, 4) == round(other.position.lat, 4) and
                round(self.position.lng, 4) == round(other.position.lng, 4))


@dataclass
class IsochroneState:
    """
    State of the isochrone propagation algorithm.
    
    Tracks all points at current time level and history for pruning.
    """
    current_isochrone: List[IsochronePoint] = field(default_factory=list)
    visited_grid: Dict[Tuple[int, int], float] = field(default_factory=dict)  # (lat_cell, lng_cell) -> best_time
    closest_distance_to_goal: float = float('inf')
    total_iterations: int = 0


# ============================================================================
# CONFIGURATION
# ============================================================================

# Angular resolution: try headings every N degrees
ANGULAR_STEP_DEFAULT = 15  # Try 24 directions (360/15)
ANGULAR_STEP_NEAR_GOAL = 10  # Finer resolution near goal

# Grid cell size for pruning (degrees)
GRID_CELL_SIZE = 0.1  # ~6 nautical miles at mid-latitudes
GRID_CELL_SIZE_NEAR_GOAL = 0.05  # Finer grid when close to goal

# Maximum isochrone size to prevent exponential explosion
MAX_ISOCHRONE_SIZE = 100  # If isochrone grows beyond this, use aggressive pruning

# Adaptive time steps (hours)
TIME_STEP_FAR = 2.0      # >50nm from goal
TIME_STEP_MEDIUM = 1.0   # 20-50nm from goal
TIME_STEP_CLOSE = 0.5    # <20nm from goal

# Directional focusing: only try headings within cone toward goal
DIRECTIONAL_CONE_ANGLE = 140  # ±140° from direct bearing (280° total)
DIRECTIONAL_CONE_ANGLE_NEAR_GOAL = 180  # No cone restriction when close to goal

# Distance thresholds for arrival
ARRIVAL_THRESHOLD_NM = 5.0  # Consider "arrived" within 5nm


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_grid_cell(position: Coordinates, cell_size: float) -> Tuple[int, int]:
    """
    Convert position to grid cell coordinates for pruning.
    
    Args:
        position: Lat/lng coordinates
        cell_size: Size of grid cell in degrees
        
    Returns:
        Tuple of (lat_cell, lng_cell) integers
    """
    lat_cell = int(position.lat / cell_size)
    lng_cell = int(position.lng / cell_size)
    return (lat_cell, lng_cell)


def get_adaptive_grid_cell_size(distance_to_goal: float) -> float:
    """
    Get grid cell size based on distance to goal.
    
    Larger cells (less aggressive pruning) when far from goal.
    Smaller cells (more aggressive pruning) when close to goal.
    """
    if distance_to_goal < 10:
        return GRID_CELL_SIZE_NEAR_GOAL
    return GRID_CELL_SIZE


def get_adaptive_time_step(distance_to_goal: float) -> float:
    """
    Select time step based on distance to goal.
    
    Closer to goal = smaller steps for accuracy.
    Far from goal = larger steps for speed.
    
    Args:
        distance_to_goal: Distance to destination in nautical miles
        
    Returns:
        Time step in hours
    """
    if distance_to_goal > 50:
        return TIME_STEP_FAR
    elif distance_to_goal > 20:
        return TIME_STEP_MEDIUM
    else:
        return TIME_STEP_CLOSE


def get_angular_step(distance_to_goal: float) -> int:
    """
    Select angular resolution based on distance to goal.
    
    Args:
        distance_to_goal: Distance to destination in nautical miles
        
    Returns:
        Angular step in degrees
    """
    if distance_to_goal < 20:
        return ANGULAR_STEP_NEAR_GOAL
    return ANGULAR_STEP_DEFAULT


def is_in_directional_cone(
    heading: float,
    destination_bearing: float,
    distance_to_goal: float,
    cone_half_angle: float = DIRECTIONAL_CONE_ANGLE
) -> bool:
    """
    Check if heading is within cone toward destination.
    
    Optimization: Don't explore directions that go significantly backward.
    Near the goal, we relax this constraint to allow final approach from any angle.
    
    Args:
        heading: Proposed heading in degrees
        destination_bearing: Bearing to goal in degrees
        distance_to_goal: Distance to goal in nautical miles
        cone_half_angle: Half-angle of cone (degrees)
        
    Returns:
        True if heading is within ±cone_half_angle of destination bearing
    """
    # Near the goal (<10nm), allow all directions for final approach
    if distance_to_goal < 10:
        return True
    
    # Calculate angular difference
    diff = abs(heading - destination_bearing)
    if diff > 180:
        diff = 360 - diff
    
    return diff <= cone_half_angle


def should_prune_point(
    point: IsochronePoint,
    state: IsochroneState,
    destination: Coordinates
) -> bool:
    """
    Decide whether to prune (discard) a point to reduce computation.
    
    Pruning strategies:
    1. Grid-based: If we've already reached this grid cell faster, prune
    2. Distance-based: If point is much farther from goal than best so far, prune
    
    Args:
        point: Point to consider
        state: Current algorithm state
        destination: Goal position
        
    Returns:
        True if point should be pruned (discarded)
    """
    # Calculate distance to goal for adaptive strategies
    distance_to_goal = calculate_distance(point.position, destination)
    
    # Strategy 1: Grid-based pruning (adaptive grid size)
    cell_size = get_adaptive_grid_cell_size(distance_to_goal)
    cell = get_grid_cell(point.position, cell_size)
    
    if cell in state.visited_grid:
        # We've been to this grid cell before
        previous_best_time = state.visited_grid[cell]
        
        # Be lenient early on (allow 10% slower times to pass through)
        time_tolerance = 0.1 if len(state.visited_grid) < 20 else 0.0
        
        if point.time_hours > previous_best_time * (1 + time_tolerance):
            # Current point is significantly slower - prune it
            return True
    
    # Update visited grid with this point (it's the best so far for this cell)
    state.visited_grid[cell] = point.time_hours
    
    # Strategy 2: Distance-based pruning
    # Update closest distance if this is better
    if distance_to_goal < state.closest_distance_to_goal:
        state.closest_distance_to_goal = distance_to_goal
    
    # Only apply distance-based pruning after we've explored sufficiently
    # This allows tacking routes that initially go "sideways" or even slightly away from goal
    if len(state.visited_grid) < 20:
        # Very early in the route: be extremely lenient to allow tacking patterns to develop
        # Only prune if point is absurdly far from goal
        if distance_to_goal > state.closest_distance_to_goal * 5.0:
            return True
    elif state.closest_distance_to_goal > 30:
        # Far from goal: moderate pruning
        if distance_to_goal > state.closest_distance_to_goal * 2.5:
            return True
    elif state.closest_distance_to_goal > 10:
        # Medium distance: moderate pruning
        if distance_to_goal > state.closest_distance_to_goal * 2.0:
            return True
    # else: Near goal (<10nm): minimal distance-based pruning, rely on grid pruning
    
    return False


def reconstruct_path(
    final_point: IsochronePoint,
    start: Coordinates,
    departure_time: datetime
) -> List[Waypoint]:
    """
    Trace back optimal path from destination to start.
    
    Walk backward through parent links, then reverse to get start→destination path.
    
    Args:
        final_point: The point that reached the destination
        start: Starting position (for validation)
        departure_time: Departure time (for waypoint timestamps)
        
    Returns:
        List of Waypoints from start to destination
    """
    # Walk backward through parents
    path_points = []
    current = final_point
    
    while current is not None:
        path_points.append(current)
        current = current.parent
    
    # Reverse to get start → destination order
    path_points.reverse()
    
    # Convert to Waypoints with timestamps
    waypoints = []
    for point in path_points:
        arrival_time = departure_time + timedelta(hours=point.time_hours)
        waypoints.append(Waypoint(
            position=Coordinates(lat=point.position.lat, lng=point.position.lng),
            estimated_arrival=arrival_time.isoformat(),
            weather=None  # Will be filled in later
        ))
    
    return waypoints


# ============================================================================
# CORE ISOCHRONE ALGORITHM
# ============================================================================

def propagate_isochrone(
    current_isochrone: List[IsochronePoint],
    destination: Coordinates,
    weather_grid: Dict,
    boat_type: str,
    time_step_hours: float,
    departure_time: datetime,
    state: IsochroneState,
    max_size: int = MAX_ISOCHRONE_SIZE
) -> List[IsochronePoint]:
    """
    Propagate isochrone forward by one time step.
    
    For each point in current isochrone:
    1. Try multiple headings
    2. Calculate boat speed using polars + weather
    3. Calculate new position after time_step_hours
    4. Prune if necessary
    5. Return new isochrone (all reachable points at next time)
    
    Args:
        current_isochrone: All points reachable at current time
        destination: Goal position
        weather_grid: Weather data grid (from weather_fetcher)
        boat_type: Type of boat ('sailboat', 'motorboat', 'catamaran')
        time_step_hours: Time interval for this step (hours)
        departure_time: Original departure time (for weather lookup)
        state: Algorithm state (for pruning)
        
    Returns:
        New isochrone: all points reachable at current_time + time_step
    """
    next_isochrone = []
    
    # Debug counters
    debug_counters = {
        'total_headings_tried': 0,
        'skipped_cone': 0,
        'skipped_no_go': 0,
        'skipped_zero_speed': 0,
        'pruned': 0,
        'added': 0
    }
    
    for point in current_isochrone:
        # Calculate bearing to destination (for directional focusing)
        destination_bearing = calculate_bearing(point.position, destination)
        
        # Calculate distance to goal (for adaptive parameters)
        distance_to_goal = calculate_distance(point.position, destination)
        
        # Get angular step size (finer resolution near goal)
        angular_step = get_angular_step(distance_to_goal)
        
        # Try multiple headings
        for heading in range(0, 360, angular_step):
            state.total_iterations += 1
            debug_counters['total_headings_tried'] += 1
            
            # Optimization 1: Skip headings outside directional cone
            if not is_in_directional_cone(heading, destination_bearing, distance_to_goal):
                debug_counters['skipped_cone'] += 1
                continue
            
            # Get weather at current position and time
            current_time = departure_time + timedelta(hours=point.time_hours)
            weather = interpolate_weather(point.position, current_time, weather_grid)
            
            if weather is None:
                continue  # No weather data available
            
            # Calculate wind angle for this heading
            wind_angle = calculate_wind_angle(heading, weather.wind_direction)
            
            # Optimization 2: Skip no-go zone (boat speed = 0)
            # For sailboats, wind angles < 45° are impossible
            if boat_type.lower() in ['sailboat', 'catamaran'] and abs(wind_angle) < 45:
                debug_counters['skipped_no_go'] += 1
                continue
            
            # Get boat speed from polar diagram
            boat_speed = get_boat_speed(weather.wind_speed, wind_angle, boat_type)
            
            if boat_speed <= 0:
                debug_counters['skipped_zero_speed'] += 1
                continue  # Can't make progress in this direction
            
            # Debug: track boat speeds for analysis
            if 'speeds' not in debug_counters:
                debug_counters['speeds'] = []
            debug_counters['speeds'].append((heading, wind_angle, boat_speed))
            
            # Calculate distance traveled in this time step
            distance_nm = boat_speed * time_step_hours
            
            # Calculate new position
            new_position = calculate_destination(point.position, heading, distance_nm)
            
            # Create new isochrone point
            new_point = IsochronePoint(
                position=new_position,
                time_hours=point.time_hours + time_step_hours,
                parent=point,
                heading=heading,
                accumulated_distance=point.accumulated_distance + distance_nm
            )
            
            # Check if we should prune this point
            if should_prune_point(new_point, state, destination):
                debug_counters['pruned'] += 1
                continue
            
            # Add to next isochrone
            next_isochrone.append(new_point)
            debug_counters['added'] += 1
    
    # Debug output if isochrone is empty or very small
    if len(next_isochrone) <= 2:
        print(f"  [DEBUG] Propagation stats:")
        print(f"    Headings tried: {debug_counters['total_headings_tried']}")
        print(f"    Skipped (cone): {debug_counters['skipped_cone']}")
        print(f"    Skipped (no-go): {debug_counters['skipped_no_go']}")
        print(f"    Skipped (zero speed): {debug_counters['skipped_zero_speed']}")
        print(f"    Pruned: {debug_counters['pruned']}")
        print(f"    Added: {debug_counters['added']}")
        if 'speeds' in debug_counters and debug_counters['speeds']:
            speeds_sample = debug_counters['speeds'][:5]  # Show first 5
            print(f"    Sample speeds (hdg, wind_ang, speed):")
            for hdg, wa, spd in speeds_sample:
                print(f"      {hdg}deg wind@{wa:.0f}deg = {spd:.1f}kt")
    
    # Safety check: if isochrone is growing too large, apply aggressive pruning
    if len(next_isochrone) > max_size:
        print(f"  [WARNING] Isochrone size ({len(next_isochrone)}) exceeds max ({max_size}), applying aggressive pruning")
        # Sort by distance to goal and keep only the best N points
        next_isochrone.sort(key=lambda p: calculate_distance(p.position, destination))
        next_isochrone = next_isochrone[:max_size]
    
    return next_isochrone


def find_arrival_point(
    isochrone: List[IsochronePoint],
    destination: Coordinates,
    threshold_nm: float = ARRIVAL_THRESHOLD_NM
) -> Optional[IsochronePoint]:
    """
    Check if any point in isochrone has reached the destination.
    
    Args:
        isochrone: Current isochrone (list of points)
        destination: Goal position
        threshold_nm: Distance threshold to consider "arrived" (nautical miles)
        
    Returns:
        The point that arrived (closest to destination if multiple), or None
    """
    arrived_points = []
    
    for point in isochrone:
        distance = calculate_distance(point.position, destination)
        if distance <= threshold_nm:
            arrived_points.append((distance, point))
    
    if not arrived_points:
        return None
    
    # Return the point closest to destination
    arrived_points.sort(key=lambda x: x[0])
    return arrived_points[0][1]


def calculate_isochrone_route(
    request: RouteRequest,
    weather_grid: Dict,
    max_time_hours: float = 120.0
) -> Optional[GeneratedRoute]:
    """
    Calculate optimal sailing route using isochrone method.
    
    This is the main entry point for isochrone routing.
    
    Args:
        request: Route request (start, end, boat_type, departure_time)
        weather_grid: Weather data grid (from fetch_regional_weather_grid)
        max_time_hours: Maximum time to propagate (hours) - prevents infinite loops
        
    Returns:
        GeneratedRoute with optimal path, or None if no route found
    """
    print(f"\n=== Starting Isochrone Route Calculation ===")
    print(f"Start: ({request.start.lat:.3f}, {request.start.lng:.3f})")
    print(f"End: ({request.end.lat:.3f}, {request.end.lng:.3f})")
    print(f"Boat: {request.boat_type.value}")
    
    # Parse departure time
    departure_time = datetime.fromisoformat(request.departure_time.replace('Z', '+00:00'))
    
    # Initialize algorithm state
    state = IsochroneState()
    
    # Create starting point
    start_point = IsochronePoint(
        position=request.start,
        time_hours=0.0,
        parent=None,
        heading=None,
        accumulated_distance=0.0
    )
    
    # Initialize first isochrone with just the start point
    state.current_isochrone = [start_point]
    state.closest_distance_to_goal = calculate_distance(request.start, request.end)
    
    print(f"Initial distance to goal: {state.closest_distance_to_goal:.1f} nm")
    
    # Propagate forward in time until we reach destination or timeout
    current_time_hours = 0.0
    
    while current_time_hours < max_time_hours:
        # Check if we've arrived
        arrival_point = find_arrival_point(state.current_isochrone, request.end)
        
        if arrival_point is not None:
            print(f"\n[SUCCESS] Destination reached!")
            print(f"  Time: {arrival_point.time_hours:.2f} hours")
            print(f"  Distance: {arrival_point.accumulated_distance:.1f} nm")
            print(f"  Iterations: {state.total_iterations}")
            
            # Reconstruct path
            waypoints = reconstruct_path(arrival_point, request.start, departure_time)
            
            # Calculate route statistics
            total_distance = arrival_point.accumulated_distance
            total_time_hours = arrival_point.time_hours
            
            return GeneratedRoute(
                name="Isochrone Optimal",
                route_type=RouteType.DIRECT,  # We'll classify it later
                waypoints=waypoints,
                distance=total_distance,
                estimated_hours=total_time_hours,
                estimated_time=format_duration(total_time_hours)
            )
        
        # Calculate adaptive time step based on distance to goal
        distance_to_goal = state.closest_distance_to_goal
        time_step = get_adaptive_time_step(distance_to_goal)
        
        print(f"\nTime: {current_time_hours:.1f}h | Isochrone: {len(state.current_isochrone)} pts | Closest: {distance_to_goal:.1f}nm | Step: {time_step:.1f}h | Visited cells: {len(state.visited_grid)}")
        
        # Propagate isochrone forward
        state.current_isochrone = propagate_isochrone(
            current_isochrone=state.current_isochrone,
            destination=request.end,
            weather_grid=weather_grid,
            boat_type=request.boat_type.value,
            time_step_hours=time_step,
            departure_time=departure_time,
            state=state
        )
        
        # Check if isochrone is empty (no reachable points - shouldn't happen)
        if not state.current_isochrone:
            print(f"\n[FAILED] Isochrone became empty - no valid paths forward")
            return None
        
        current_time_hours += time_step
    
    print(f"\n[TIMEOUT] Reached {max_time_hours} hours without finding destination")
    print(f"  Closest approach: {state.closest_distance_to_goal:.1f} nm")
    
    return None


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_isochrone_routes(request: RouteRequest) -> List[GeneratedRoute]:
    """
    Generate optimal sailing routes using isochrone method.
    
    Returns up to 3 route variations:
    1. Fastest route (optimal time)
    2. Shortest route (optimal distance, if different from fastest)
    3. Safest route (avoids high winds/waves, if significantly different)
    
    Args:
        request: Route request with start, end, boat_type, departure_time
        
    Returns:
        List of GeneratedRoute objects (1-3 routes)
    """
    print(f"\n{'='*60}")
    print(f"ISOCHRONE ROUTE GENERATION")
    print(f"{'='*60}")
    
    # Calculate route bounds and fetch weather grid
    direct_distance = calculate_distance(request.start, request.end)
    forecast_hours = calculate_forecast_hours_needed(direct_distance, avg_boat_speed=6.0)
    
    print(f"\nFetching weather grid...")
    print(f"  Forecast hours: {forecast_hours}")
    
    weather_grid = fetch_regional_weather_grid(
        start=request.start,
        end=request.end,
        departure_time=request.departure_time,
        grid_spacing=10.0,  # 10nm grid spacing
        forecast_hours=forecast_hours
    )
    
    print(f"  Grid points: {len(weather_grid.get('points', []))}")
    
    # Check if we have weather data
    if not weather_grid.get('points'):
        print("\n[ERROR] No weather data available - cannot calculate route")
        return []
    
    # Calculate primary route (fastest)
    primary_route = calculate_isochrone_route(request, weather_grid)
    
    if primary_route is None:
        print("\n[FAILED] No valid route found")
        return []
    
    routes = [primary_route]
    
    # TODO: Generate variations (shortest, safest)
    # For now, just return the optimal route
    # Future enhancement: modify algorithm to prioritize different objectives
    
    print(f"\n{'='*60}")
    print(f"Generated {len(routes)} isochrone route(s)")
    print(f"{'='*60}\n")
    
    return routes


# ============================================================================
# TESTING / DEBUG
# ============================================================================

if __name__ == "__main__":
    print("Isochrone Router - Test Mode")
    print("=" * 60)
    
    # Test case: Southampton to Cherbourg (classic sailing route)
    from models import RouteRequest, Coordinates, BoatType
    
    test_request = RouteRequest(
        start=Coordinates(lat=50.9, lng=-1.4),  # Southampton
        end=Coordinates(lat=49.6, lng=-1.6),    # Cherbourg
        boat_type=BoatType.SAILBOAT,
        departure_time="2024-01-15T08:00:00Z"
    )
    
    print("\nTest Route: Southampton -> Cherbourg")
    print(f"Distance: {calculate_distance(test_request.start, test_request.end):.1f} nm")
    
    routes = generate_isochrone_routes(test_request)
    
    if routes:
        print(f"\n[SUCCESS] Generated {len(routes)} route(s)")
        for i, route in enumerate(routes, 1):
            print(f"\nRoute {i}: {route.name}")
            print(f"  Distance: {route.total_distance:.1f} nm")
            print(f"  Time: {route.estimated_hours:.1f} hours")
            print(f"  Waypoints: {len(route.waypoints)}")
    else:
        print("\n[FAILED] No routes generated")

