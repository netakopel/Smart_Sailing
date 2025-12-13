"""
Debug script to understand pruning behavior
"""

import logging
from datetime import datetime, timedelta, timezone
from models import RouteRequest, Coordinates, BoatType, WaypointWeather
from isochrone_router import (
    calculate_isochrone_route, IsochronePoint, IsochroneState,
    should_prune_point, get_grid_cell, GRID_CELL_SIZE
)
from route_generator import calculate_distance

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create simple mock weather grid
def create_mock_weather_grid(start, end, wind_direction=0.0):
    min_lat = min(start.lat, end.lat) - 1
    max_lat = max(start.lat, end.lat) + 1
    min_lng = min(start.lng, end.lng) - 1
    max_lng = max(start.lng, end.lng) + 1
    
    lat_step = (max_lat - min_lat) / 2
    lng_step = (max_lng - min_lng) / 2
    
    grid_points = []
    for i in range(3):
        for j in range(3):
            lat = min_lat + i * lat_step
            lng = min_lng + j * lng_step
            grid_points.append((lat, lng))
    
    base_time = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
    times = [base_time + timedelta(hours=h) for h in range(24)]
    
    weather_data = {}
    for lat, lng in grid_points:
        for time_idx in range(len(times)):
            weather_data[(lat, lng, time_idx)] = WaypointWeather(
                wind_speed=15.0,
                wind_direction=wind_direction,
                wave_height=1.5,
                precipitation=0.0,
                visibility=15.0,
                temperature=18.0,
                wind_gusts=18.0,
                wind_sustained=15.0,
                is_estimated=False
            )
    
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


logger.info("="*70)
logger.info("PRUNING LOGIC DEBUG")
logger.info("="*70)

# Test scenario: upwind (headwind)
start = Coordinates(lat=50.5, lng=-1.0)
end = Coordinates(lat=50.0, lng=-1.0)

logger.info(f"\nScenario: Sailing SOUTH (upwind)")
logger.info(f"Start: {start.lat}N, {start.lng}E")
logger.info(f"End:   {end.lat}N, {end.lng}E")
logger.info(f"Distance: {calculate_distance(start, end):.1f}nm")
logger.info(f"Wind: 15kt from NORTH (directly against us)")
logger.info()

# Simulate what happens after first propagation
logger.info("-"*70)
logger.info("SIMULATION: After 1 hour of sailing")
logger.info("-"*70)

# Create sample points from different headings
state = IsochroneState()
state.closest_distance_to_goal = 30.0  # Haven't gotten closer yet

# Simulate 5 points that survived first propagation
sample_points = [
    IsochronePoint(Coordinates(lat=50.6, lng=-1.1), time_hours=1.0, accumulated_distance=8.0),  # NW
    IsochronePoint(Coordinates(lat=50.6, lng=-0.9), time_hours=1.0, accumulated_distance=8.0),  # NE
    IsochronePoint(Coordinates(lat=50.5, lng=-1.2), time_hours=1.0, accumulated_distance=9.0),  # W
    IsochronePoint(Coordinates(lat=50.5, lng=-0.8), time_hours=1.0, accumulated_distance=9.0),  # E
    IsochronePoint(Coordinates(lat=50.4, lng=-1.0), time_hours=1.0, accumulated_distance=7.0),  # S
]

logger.info(f"\n5 points reached after 1 hour:")
for i, pt in enumerate(sample_points, 1):
    dist = calculate_distance(pt.position, end)
    cell = get_grid_cell(pt.position, GRID_CELL_SIZE)
    logger.info(f"  Point {i}: ({pt.position.lat:.2f}, {pt.position.lng:.2f}) "
          f"= {dist:.1f}nm from goal, cell={cell}")
    
    # Add to visited grid
    state.visited_grid[cell] = pt.time_hours

logger.info(f"\nVisited grid now has {len(state.visited_grid)} cells")
logger.info(f"Closest to goal: {state.closest_distance_to_goal:.1f}nm")

# Now simulate propagating from ONE of these points
logger.info("\n" + "-"*70)
logger.info("SIMULATION: Propagating from Point 5 (the southern one)")
logger.info("-"*70)

current_point = sample_points[4]  # The southern point at 50.4N
logger.info(f"Current position: ({current_point.position.lat:.2f}, {current_point.position.lng:.2f})")
logger.info(f"Current time: {current_point.time_hours:.1f}h")
logger.info()

# Try a few sample headings
test_headings = [
    (150, "SSE - toward goal but still oblique"),
    (180, "South - directly toward goal"),
    (210, "SSW - toward goal but still oblique"),
]

for heading, description in test_headings:
    # Simulate new point after sailing for 1 more hour at ~8 knots
    # Rough calculation: move 8nm in the heading direction
    import math
    lat_change = (8 / 60) * math.cos(math.radians(heading))
    lng_change = (8 / 60) * math.sin(math.radians(heading)) / math.cos(math.radians(current_point.position.lat))
    
    new_lat = current_point.position.lat + lat_change
    new_lng = current_point.position.lng + lng_change
    
    new_point = IsochronePoint(
        position=Coordinates(lat=new_lat, lng=new_lng),
        time_hours=2.0,
        parent=current_point,
        accumulated_distance=current_point.accumulated_distance + 8.0
    )
    
    dist_to_goal = calculate_distance(new_point.position, end)
    cell = get_grid_cell(new_point.position, GRID_CELL_SIZE)
    
    logger.info(f"\nHeading {heading}deg ({description}):")
    logger.info(f"  New position: ({new_lat:.2f}, {new_lng:.2f})")
    logger.info(f"  Distance to goal: {dist_to_goal:.1f}nm")
    logger.info(f"  Grid cell: {cell}")
    logger.info(f"  Cell in visited_grid? {cell in state.visited_grid}")
    
    if cell in state.visited_grid:
        prev_time = state.visited_grid[cell]
        logger.info(f"  Previous best time to this cell: {prev_time:.1f}h")
        logger.info(f"  Current time: {new_point.time_hours:.1f}h")
        logger.info(f"  Is current slower? {new_point.time_hours} > {prev_time * 1.1:.2f}? {new_point.time_hours > prev_time * 1.1}")
    
    # Test pruning
    should_prune = should_prune_point(new_point, state, end)
    logger.info(f"  => PRUNED? {should_prune}")

logger.info("\n" + "="*70)
logger.info("DIAGNOSIS")
logger.info("="*70)
logger.info("""
The problem: Points we're trying to explore have ALREADY been visited
by other branches at an earlier time, so they get pruned as "slower".

This is CORRECT behavior for the grid-based pruning!

The REAL issue: We didn't keep enough diverse points at time=1h.
We only kept 1 point, so it has nowhere new to go.

Solution: Be more lenient in early propagation to keep more exploration paths open.
""")

