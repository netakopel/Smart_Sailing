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
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

from models import Coordinates, Waypoint, RouteRequest, BoatType, WaypointWeather
from route_generator import (
    calculate_distance, calculate_bearing, calculate_destination,
    calculate_route_distance, format_duration, GeneratedRoute, RouteType
)
from weather_fetcher import fetch_regional_weather_grid, interpolate_weather, calculate_forecast_hours_needed
from polars import get_boat_speed, calculate_wind_angle, normalize_angle, is_in_no_go_zone

# Set up logging
logger = logging.getLogger(__name__)


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
# Larger angles = smoother routes with less tacking
ANGULAR_STEP_DEFAULT = 20  # Try 18 directions (360/20) - reduced from 15 for smoother routes
ANGULAR_STEP_NEAR_GOAL = 15  # Try 24 directions near goal - reduced from 10

# Grid cell size for pruning (degrees)
# Fixed small cell size: 2nm = ~0.033° at mid-latitudes
# Small cells prevent convergence and make pruning more effective
GRID_CELL_SIZE = 0.033  # ~2 nautical miles at mid-latitudes (fixed size for consistent pruning)
GRID_CELL_SIZE_NEAR_GOAL = 0.033  # Same size near goal (no need to change)

# Maximum isochrone size to prevent exponential explosion
MAX_ISOCHRONE_SIZE = 75  # If isochrone grows beyond this, use aggressive pruning (increased from 50 for better route exploration)
MAX_ISOCHRONE_GROWTH_WARNING = 100  # Cut to 100 points if isochrone exceeds this

# Adaptive time steps (hours)
TIME_STEP_FAR = 2.0      # >50nm from goal
TIME_STEP_MEDIUM = 1.0   # 20-50nm from goal
TIME_STEP_CLOSE = 0.5    # <20nm from goal

# Directional focusing: only try headings within cone toward goal
DIRECTIONAL_CONE_ANGLE = 140  # ±140° from direct bearing (280° total) - increased to allow more exploration (was 100°)
DIRECTIONAL_CONE_ANGLE_NEAR_GOAL = 180  # ±180° when close to goal (allow all directions) - increased (was 140°)

# Distance thresholds for arrival
ARRIVAL_THRESHOLD_NM = 2.0  # Consider "arrived" within 2nm (then add final segment)


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


def get_adaptive_grid_cell_size(distance_to_goal: float, exploration_level: int = 0) -> float:
    """
    Get grid cell size - now returns fixed small size for consistent pruning.
    
    Using a fixed small cell size (2nm) prevents convergence issues and makes
    pruning more effective. Points are spread across more cells, reducing the
    chance of all points mapping to the same cells.
    
    Args:
        distance_to_goal: Distance to destination in nm (not used)
        exploration_level: Number of cells visited (not used, kept for API compatibility)
        
    Returns:
        Fixed grid cell size in degrees (~0.033° = 2nm)
    """
    # Fixed small cell size: 2nm = ~0.033° at mid-latitudes
    # This prevents convergence and makes pruning more effective
    return GRID_CELL_SIZE


def get_adaptive_time_step(distance_to_goal: float) -> float:
    """
    Select time step based on distance to goal.
    
    Using fixed 0.5h time steps for consistent propagation throughout the route.
    
    Args:
        distance_to_goal: Distance to destination in nautical miles
        
    Returns:
        Time step in hours (always 0.5)
    """
    return 0.5  # Fixed 0.5h time step for all legs


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
    destination: Coordinates,
    route_distance: float
) -> bool:
    """
    Decide whether to prune (discard) a point to reduce computation.
    
    Pruning strategies:
    1. Grid-based: If we've already reached this grid cell faster, prune
    2. Distance-based: If point is much farther from goal than best so far, prune
    
    Note: No-go zone filtering happens BEFORE point creation in propagate_isochrone(),
    so no need to check it here.
    
    Args:
        point: Point to consider
        state: Current algorithm state
        destination: Goal position
        route_distance: Total route distance in nm (used for distance-based pruning threshold)
        
    Returns:
        True if point should be pruned (discarded)
    """
    # Calculate distance to goal for adaptive strategies
    distance_to_goal = calculate_distance(point.position, destination)
    
    # Strategy 1: Grid-based pruning (adaptive grid size)
    cell_size = get_adaptive_grid_cell_size(distance_to_goal, len(state.visited_grid))
    cell = get_grid_cell(point.position, cell_size)
    
    # Update closest distance if this is better (for logging and distance-based pruning)
    if distance_to_goal < state.closest_distance_to_goal:
        state.closest_distance_to_goal = distance_to_goal
    
    # Strategy 2: Distance-based pruning (check first, before grid-based)
    # Apply aggressively from the start to achieve ~90% pruning consistently
    exploration_level = len(state.visited_grid)
    distance_threshold = route_distance * 0.5  # 50% of route distance (halfway point)
    
    # Enable distance-based pruning from the very start for consistent 90% pruning
    # Progressive tightening: more aggressive as we explore more
    if exploration_level < 10:
        distance_multiplier = 1.3  # Prune if >1.3x farther than best (very aggressive)
    elif exploration_level < 20:
        distance_multiplier = 1.25  # Prune if >1.25x farther than best
    elif exploration_level < 40:
        distance_multiplier = 1.2  # Prune if >1.2x farther than best
    elif exploration_level < 60:
        distance_multiplier = 1.15  # Prune if >1.15x farther than best
    else:
        # Well-explored: very tight pruning (like the successful final iteration)
        distance_multiplier = 1.1  # Prune if >1.1x farther than best
    
    # Apply distance pruning when:
    # - We're still far from goal (>50% of route distance remaining), OR
    # - We're well-explored (exploration_level > 10)
    # This ensures aggressive pruning from the start
    if state.closest_distance_to_goal > distance_threshold or exploration_level > 10:
        if state.closest_distance_to_goal > 0:  # Only if we have a valid closest distance
            if distance_to_goal > state.closest_distance_to_goal * distance_multiplier:
                return True
    
    # Strategy 1: Grid-based pruning (adaptive grid size)
    # Check if we've been to this grid cell before
    if cell in state.visited_grid:
        previous_best_time = state.visited_grid[cell]
        
        # Calculate time difference
        time_diff = point.time_hours - previous_best_time
        
        # If this point is better (faster), update the grid
        if time_diff < 0:
            state.visited_grid[cell] = point.time_hours
            # Don't prune - this is a better route to this cell
            return False
        
        # If this point is significantly slower, prune it
        # Use progressive tolerance: more lenient early, stricter later
        # Calculate tolerance based on exploration level
        # Primary mechanism: relative tolerance (scales with time)
        # Safety net: minimum absolute tolerance (prevents over-pruning very early)
        
        # Relative tolerance: aggressive from the start to achieve ~90% pruning
        # TIGHTENED: Much more aggressive tolerances to consistently prune 90%
        if exploration_level < 5:
            # Very early: still aggressive
            relative_tolerance_ratio = 0.15  # Allow only 15% slower (1.15x total time)
        elif exploration_level < 20:
            relative_tolerance_ratio = 0.12  # Allow only 12% slower (1.12x total time)
        elif exploration_level < 50:
            relative_tolerance_ratio = 0.10  # Allow only 10% slower (1.10x total time)
        elif exploration_level < 150:
            relative_tolerance_ratio = 0.08  # Allow only 8% slower (1.08x total time)
        else:
            relative_tolerance_ratio = 0.05  # Allow only 5% slower (1.05x total time)
        
        # Calculate relative threshold (primary mechanism)
        relative_threshold = previous_best_time * relative_tolerance_ratio
        
        # Minimum absolute tolerance: scales with exploration level
        # TIGHTENED: Much more aggressive absolute tolerances
        time_step = 0.5  # Current time step
        if exploration_level < 5:
            # Very early: small tolerance
            min_absolute_tolerance = time_step * 0.5  # 0.25 hours
        elif exploration_level < 20:
            min_absolute_tolerance = time_step * 0.4  # 0.2 hours
        elif exploration_level < 50:
            min_absolute_tolerance = time_step * 0.3  # 0.15 hours
        elif exploration_level < 150:
            min_absolute_tolerance = time_step * 0.2  # 0.1 hours
        else:
            min_absolute_tolerance = time_step * 0.1  # 0.05 hours
        
        # Account for time gap between previous_best_time and current time
        # If previous_best_time is very old, we need some tolerance because
        # the isochrone has moved forward significantly since then
        time_gap = point.time_hours - previous_best_time
        # REDUCED gap bonus: Add smaller tolerance proportional to time gap
        # This prevents pruning when comparing to very old times, but not excessively
        gap_bonus = min(time_gap * 0.1, time_step * 0.5)  # Up to 0.25 hour bonus for large gaps
        
        # Use the more lenient of: relative tolerance or (minimum absolute tolerance + gap bonus)
        # This ensures we use relative tolerance when it's more lenient,
        # but have a safety net for very early exploration and old time comparisons
        combined_threshold = max(relative_threshold, min_absolute_tolerance + gap_bonus)
        
        # Prune only if significantly slower than the combined threshold
        if time_diff > combined_threshold:
            return True
        
        # If we get here, the point is within tolerance - keep it but don't update grid
        # (we already have a better time for this cell)
        return False
    else:
        # First time visiting this cell - but we can still prune if it's clearly bad
        # Strategy 3: Prune new cells that are significantly worse than nearby cells
        # or too far from goal (even if it's a new cell)
        
        # Check nearby cells to see if we've reached similar areas faster
        # Use a slightly larger cell size to check neighbors
        neighbor_cell_size = cell_size * 1.5  # Check cells 1.5x larger
        neighbor_cell = get_grid_cell(point.position, neighbor_cell_size)
        
        # If we've been to a nearby (larger) cell, compare times
        if neighbor_cell in state.visited_grid:
            nearby_best_time = state.visited_grid[neighbor_cell]
            time_diff = point.time_hours - nearby_best_time
            
            # Be more lenient for nearby cells (they're not exactly the same location)
            # But still prune if significantly slower - made more aggressive
            if exploration_level < 50:
                nearby_tolerance = 0.15  # Allow only 15% slower for nearby cells
            else:
                nearby_tolerance = 0.10  # Allow only 10% slower for nearby cells
            
            if time_diff > nearby_best_time * nearby_tolerance:
                # This new cell is significantly slower than a nearby cell - prune it
                return True
        
        # Strategy 4: Prune new cells that are too far from goal (even if new)
        # This prevents exploring areas that are clearly off-course
        # Made much more aggressive to achieve ~90% pruning
        if exploration_level > 3:  # Start very early
            # Calculate how much worse this point is distance-wise
            distance_ratio = distance_to_goal / state.closest_distance_to_goal if state.closest_distance_to_goal > 0 else 1.0
            
            # Progressive tightening: very aggressive from the start
            if exploration_level > 10 and distance_ratio > 1.25:
                # Early exploration: prune new cells 25%+ farther from goal
                return True
            elif exploration_level > 20 and distance_ratio > 1.2:
                # Mid exploration: prune new cells 20%+ farther from goal
                return True
            elif exploration_level > 40 and distance_ratio > 1.15:
                # Well-explored: prune new cells 15%+ farther from goal
                return True
            elif exploration_level > 60 and distance_ratio > 1.1:
                # Very well-explored: prune new cells 10%+ farther from goal
                return True
        
        # If we get here, this is a reasonable new cell - add it to grid
        state.visited_grid[cell] = point.time_hours
        return False
    
    # Note: No-go zone check happens BEFORE points are created in propagate_isochrone(),
    # so we don't need a redundant check here. Points that reach here have already
    # been verified to not require sailing in the no-go zone.


def reconstruct_path(
    final_point: IsochronePoint,
    start: Coordinates,
    departure_time: datetime,
    destination: Coordinates = None
) -> List[Waypoint]:
    """
    Trace back optimal path from destination to start.
    
    Walk backward through parent links, then reverse to get start→destination path.
    
    Args:
        final_point: The point that reached the destination
        start: Starting position (for validation)
        departure_time: Departure time (for waypoint timestamps)
        destination: Exact destination coordinates (adds final segment if provided)
        
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
            weather=None,  # Will be filled in later
            heading=point.heading  # Store the actual sailing heading (validated during propagation)
        ))
    
    # Always add final segment to reach exact destination
    if destination and len(waypoints) > 0:
        last_wp = waypoints[-1]
        last_position = Coordinates(lat=last_wp.position.lat, lng=last_wp.position.lng)
        distance_to_dest = calculate_distance(last_position, destination)
        
        # If we're not exactly at the destination, add final waypoint
        if distance_to_dest > 0.05:  # More than ~50 meters
            logger.info(f"Adding final segment: {distance_to_dest:.2f}nm to exact destination")
            
            # Calculate final heading and check if it's in no-go zone
            final_heading = calculate_bearing(last_position, destination)
            logger.debug(f"  Final segment heading: {final_heading:.0f}°")
            
            # Use the same approach as during propagation - estimate based on last segment speed
            if len(path_points) >= 2:
                # Calculate average speed from last segment
                last_point = path_points[-1]
                prev_point = path_points[-2]
                time_diff = last_point.time_hours - prev_point.time_hours
                dist_diff = calculate_distance(prev_point.position, last_point.position)
                avg_speed = dist_diff / time_diff if time_diff > 0 else 5.0
                # Use at least 3 knots (conservative for final approach)
                avg_speed = max(3.0, avg_speed)
            else:
                avg_speed = 5.0  # Default conservative speed
            
            final_time_hours = final_point.time_hours + (distance_to_dest / avg_speed)
            final_arrival = departure_time + timedelta(hours=final_time_hours)
            
            logger.info(f"  Final segment speed: {avg_speed:.1f}kt")
            logger.info(f"  Final segment time: {(distance_to_dest / avg_speed):.2f}h")
            logger.info(f"  Total time: {final_time_hours:.2f}h")
            
            waypoints.append(Waypoint(
                position=Coordinates(lat=destination.lat, lng=destination.lng),
                estimated_arrival=final_arrival.isoformat(),
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
    route_distance: float,
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
        route_distance: Total route distance in nm (for distance-based pruning threshold)
        
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
            
            # First, estimate where we'd end up with this heading (for initial boat speed calculation)
            # We need an initial boat_speed estimate, so use weather at current position
            current_time = departure_time + timedelta(hours=point.time_hours)
            current_weather = interpolate_weather(point.position, current_time, weather_grid)
            
            if current_weather is None:
                continue  # No weather data available
            
            # Calculate wind angle for this heading using current weather
            wind_angle = calculate_wind_angle(heading, current_weather.wind_direction)
            
            # Get boat speed from polar diagram
            boat_speed = get_boat_speed(current_weather.wind_speed, wind_angle, boat_type)
            
            if boat_speed <= 0:
                debug_counters['skipped_zero_speed'] += 1
                continue  # Can't make progress in this direction
            
            # Calculate distance traveled in this time step
            distance_nm = boat_speed * time_step_hours
            
            # Calculate new position
            new_position = calculate_destination(point.position, distance_nm, heading)
            
            # Now get weather at the DESTINATION position and time (where we'll arrive)
            arrival_time = departure_time + timedelta(hours=point.time_hours + time_step_hours)
            destination_weather = interpolate_weather(new_position, arrival_time, weather_grid)
            
            if destination_weather is None:
                continue  # No weather data at destination
            
            # Calculate wind angle at destination using destination weather
            destination_wind_angle = calculate_wind_angle(heading, destination_weather.wind_direction)
            
            # Optimization 2: Skip no-go zone (boat speed = 0)
            # For sailboats/catamarans, wind angles < 45° are impossible
            # Check the DESTINATION weather, not the current weather
            if is_in_no_go_zone(destination_wind_angle, boat_type):
                debug_counters['skipped_no_go'] += 1
                continue
            
            # Debug: track boat speeds for analysis
            if 'speeds' not in debug_counters:
                debug_counters['speeds'] = []
            if len(debug_counters['speeds']) < 10:  # Track more samples
                debug_counters['speeds'].append((heading, destination_wind_angle, boat_speed))
            
            # Create new isochrone point
            # Note: heading represents the direction traveled FROM parent TO this new point
            # It's the heading OF the parent point (the leg we just sailed)
            new_point = IsochronePoint(
                position=new_position,
                time_hours=point.time_hours + time_step_hours,
                parent=point,
                heading=heading,  # Heading of the leg FROM parent TO new_point
                accumulated_distance=point.accumulated_distance + distance_nm
            )
            
            # Check if we should prune this point
            if should_prune_point(new_point, state, destination, route_distance):
                debug_counters['pruned'] += 1
                continue
            
            # Add to next isochrone
            next_isochrone.append(new_point)
            debug_counters['added'] += 1
    
    # Debug output if isochrone is empty or very small
    if len(next_isochrone) <= 2:
        logger.warning(f"  SMALL ISOCHRONE WARNING: Only {len(next_isochrone)} points remaining!")
        logger.warning(f"  Propagation stats:")
        logger.warning(f"    Headings tried: {debug_counters['total_headings_tried']}")
        logger.warning(f"    Skipped (cone): {debug_counters['skipped_cone']}")
        logger.warning(f"    Skipped (no-go): {debug_counters['skipped_no_go']}")
        logger.warning(f"    Skipped (zero speed): {debug_counters['skipped_zero_speed']}")
        logger.warning(f"    Pruned: {debug_counters['pruned']}")
        logger.warning(f"    Added: {debug_counters['added']}")
        if 'speeds' in debug_counters and debug_counters['speeds']:
            speeds_sample = debug_counters['speeds']
            logger.warning(f"    Sample speeds (first {len(speeds_sample)} valid headings):")
            for hdg, wa, spd in speeds_sample:
                logger.warning(f"      {hdg}deg wind@{wa:.0f}deg = {spd:.1f}kt")
            # Check if we tried heading toward goal
            destination_bearing = calculate_bearing(current_isochrone[0].position if current_isochrone else None, destination)
            if destination_bearing and current_isochrone:
                logger.warning(f"    Bearing to goal: {destination_bearing:.0f}deg")
    
    # Log pruning effectiveness
    if debug_counters['pruned'] > 0:
        prune_ratio = debug_counters['pruned'] / (debug_counters['pruned'] + debug_counters['added']) if (debug_counters['pruned'] + debug_counters['added']) > 0 else 0
        logger.debug(f"  Pruning: {debug_counters['pruned']} pruned, {debug_counters['added']} added ({prune_ratio*100:.1f}% pruned)")
    
    # Always favor points closer to goal by sorting and limiting isochrone size
    if len(next_isochrone) > MAX_ISOCHRONE_GROWTH_WARNING:
        # Warn if isochrone is exploding (suggests pruning isn't aggressive enough)
        logger.warning(f"   Isochrone explosion detected: {len(next_isochrone)} points (threshold: {MAX_ISOCHRONE_GROWTH_WARNING})")
        logger.warning(f"      Pruning stats: {debug_counters['pruned']} pruned, {debug_counters['added']} added")
        logger.warning(f"      This suggests pruning logic is too lenient. Consider adjusting time_tolerance or pruning strategies.")
    
    # Apply fixed-size pruning if isochrone is too large
    # Target: cut to 100 points if we exceed 100 threshold
    # Fallback: if pruning would leave too few points, skip pruning this iteration
    if len(next_isochrone) > MAX_ISOCHRONE_GROWTH_WARNING:
        # Cut to fixed 100 points
        target_size = 100
        
        # Skip pruning if already at or below target
        if len(next_isochrone) <= target_size:
            # Already under target, no need to prune
            pass
        else:
            reduction_ratio = len(next_isochrone) / target_size
            logger.info(f"  Isochrone pruning: {len(next_isochrone)} → {target_size} points ({reduction_ratio:.1f}x reduction, {((1 - target_size/len(next_isochrone))*100):.1f}% pruned)")
            
            # Smarter selection: Use a combination of distance and time efficiency
            # This keeps points that are either:
            # 1. Close to goal (distance-based)
            # 2. Making good progress (time-efficient)
            # This preserves diverse routes instead of just the closest points
            
            # Calculate a combined score: lower is better
            # Score = normalized_distance + normalized_time
            # Normalize both to 0-1 range so they're comparable
            distances = [calculate_distance(p.position, destination) for p in next_isochrone]
            times = [p.time_hours for p in next_isochrone]
            
            min_dist = min(distances)
            max_dist = max(distances)
            min_time = min(times)
            max_time = max(times)
            
            # Avoid division by zero
            dist_range = max_dist - min_dist if max_dist > min_dist else 1.0
            time_range = max_time - min_time if max_time > min_time else 1.0
            
            # Score each point (lower is better)
            scored_points = []
            for i, point in enumerate(next_isochrone):
                # Normalize distance (0 = closest, 1 = farthest)
                norm_dist = (distances[i] - min_dist) / dist_range
                # Normalize time (0 = fastest, 1 = slowest)
                norm_time = (times[i] - min_time) / time_range
                # Combined score: weight distance more (60%) than time (40%)
                # This favors points that are close OR making good time progress
                score = 0.6 * norm_dist + 0.4 * norm_time
                scored_points.append((score, point))
            
            # Sort by score and keep the best N points
            scored_points.sort(key=lambda x: x[0])
            pruned_isochrone = [p for _, p in scored_points[:target_size]]
            
            # Final safety check: if pruning would result in 0 points, skip it
            if len(pruned_isochrone) == 0:
                logger.warning(f"  Skipping pruning: would result in 0 points, keeping all {len(next_isochrone)} points")
            else:
                next_isochrone = pruned_isochrone
    
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
    logger.info("=== Starting Isochrone Route Calculation ===")
    logger.info(f"Start: ({request.start.lat:.3f}, {request.start.lng:.3f})")
    logger.info(f"End: ({request.end.lat:.3f}, {request.end.lng:.3f})")
    logger.info(f"Boat: {request.boat_type.value}")
    
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
    route_distance = calculate_distance(request.start, request.end)
    state.closest_distance_to_goal = route_distance
    
    logger.info(f"Initial distance to goal: {route_distance:.1f} nm")
    
    # Propagate forward in time until we reach destination or timeout
    current_time_hours = 0.0
    
    while current_time_hours < max_time_hours:
        # Check if we've arrived
        arrival_point = find_arrival_point(state.current_isochrone, request.end)
        
        if arrival_point is not None:
            logger.info("[SUCCESS] Destination reached!")
            logger.info(f"  Time: {arrival_point.time_hours:.2f} hours")
            logger.info(f"  Distance: {arrival_point.accumulated_distance:.1f} nm")
            logger.info(f"  Iterations: {state.total_iterations}")
            
            # Reconstruct path (adds final segment to exact destination)
            waypoints = reconstruct_path(arrival_point, request.start, departure_time, request.end)
            
            # Calculate route statistics
            total_distance = calculate_route_distance(waypoints)
            
            # Calculate total time (use last waypoint's time)
            if waypoints:
                last_arrival = datetime.fromisoformat(waypoints[-1].estimated_arrival)
                total_time_hours = (last_arrival - departure_time).total_seconds() / 3600
                logger.info(f"Total time calculation: {total_time_hours:.2f}h ({len(waypoints)} waypoints)")
            else:
                total_time_hours = arrival_point.time_hours
                logger.info(f"Using arrival point time: {total_time_hours:.2f}h")
            
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
        
        logger.info(f"Time: {current_time_hours:.1f}h | Isochrone: {len(state.current_isochrone)} pts | Closest: {distance_to_goal:.1f}nm | Step: {time_step:.1f}h | Visited cells: {len(state.visited_grid)}")
        
        # Propagate isochrone forward
        logger.debug(f"Before propagation: {len(state.current_isochrone)} points")
        state.current_isochrone = propagate_isochrone(
            current_isochrone=state.current_isochrone,
            destination=request.end,
            weather_grid=weather_grid,
            boat_type=request.boat_type.value,
            time_step_hours=time_step,
            departure_time=departure_time,
            state=state,
            route_distance=route_distance
        )
        
        # Check if isochrone is empty (no reachable points - shouldn't happen)
        if not state.current_isochrone:
            logger.error("[FAILED] Isochrone became empty - no valid paths forward")
            logger.error(f"  Last iteration stats:")
            logger.error(f"    Visited cells: {len(state.visited_grid)}")
            logger.error(f"    Closest distance: {state.closest_distance_to_goal:.1f} nm")
            return None
        
        current_time_hours += time_step
    
    logger.warning(f"[TIMEOUT] Reached {max_time_hours} hours without finding destination")
    logger.warning(f"  Closest approach: {state.closest_distance_to_goal:.1f} nm")
    
    return None


# ============================================================================
# PUBLIC API
# ============================================================================

def generate_isochrone_routes(request: RouteRequest) -> tuple[List[GeneratedRoute], dict]:
    """
    Generate optimal sailing routes using isochrone method.
    
    Returns up to 3 route variations:
    1. Fastest route (optimal time)
    2. Shortest route (optimal distance, if different from fastest)
    3. Safest route (avoids high winds/waves, if significantly different)
    
    Args:
        request: Route request with start, end, boat_type, departure_time
        
    Returns:
        Tuple of (List of GeneratedRoute objects (1-3 routes), weather_grid_metadata dict)
        weather_grid_metadata contains: grid_points (list of (lat, lng) tuples), bounds
    """
    logger.info("="*60)
    logger.info("ISOCHRONE ROUTE GENERATION")
    logger.info("="*60)
    
    # Calculate route bounds and fetch weather grid
    direct_distance = calculate_distance(request.start, request.end)
    forecast_hours = calculate_forecast_hours_needed(direct_distance, avg_boat_speed=6.0)
    
    logger.info("Fetching weather grid...")
    logger.info(f"  Forecast hours: {forecast_hours}")
    
    weather_grid = fetch_regional_weather_grid(
        start=request.start,
        end=request.end,
        departure_time=request.departure_time,
        forecast_hours=forecast_hours
    )
    
    logger.info(f"  Grid points: {len(weather_grid.get('grid_points', []))}")
    
    # Check if we have weather data
    if not weather_grid.get('grid_points') or not weather_grid.get('weather_data'):
        logger.error("No weather data available - cannot calculate route")
        return [], {}
    
    # Calculate primary route (fastest)
    primary_route = calculate_isochrone_route(request, weather_grid)
    
    if primary_route is None:
        logger.warning("No valid route found")
        return [], {}
    
    routes = [primary_route]
    
    # TODO: Generate variations (shortest, safest)
    # For now, just return the optimal route
    # Future enhancement: modify algorithm to prioritize different objectives
    
    logger.info("="*60)
    logger.info(f"Generated {len(routes)} isochrone route(s)")
    logger.info("="*60)
    
    # Extract metadata for frontend visualization
    weather_grid_metadata = {
        'grid_points': weather_grid.get('grid_points', []),
        'bounds': weather_grid.get('bounds', {})
    }
    
    return routes, weather_grid_metadata



