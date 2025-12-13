"""
Test if heading 180° is actually being added to the first isochrone
"""

import logging
from datetime import datetime, timezone, timedelta
from models import Coordinates, WaypointWeather
from isochrone_router import (
    IsochronePoint, IsochroneState, should_prune_point,
    get_grid_cell, GRID_CELL_SIZE
)
from route_generator import calculate_distance, calculate_destination
from polars import get_boat_speed, calculate_wind_angle

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logger.info("="*70)
logger.info("TEST: Why isn't heading 180deg making progress?")
logger.info("="*70)

start = Coordinates(lat=50.5, lng=-1.0)
end = Coordinates(lat=50.0, lng=-1.0)

logger.info(f"\nStart: {start.lat}N, {start.lng}E")
logger.info(f"End: {end.lat}N, {end.lng}E")
logger.info(f"Distance: {calculate_distance(start, end):.1f}nm")
logger.info()

# Simulate first propagation: heading 180° from start
state = IsochroneState()
state.closest_distance_to_goal = 30.0

# Wind from north (0°)
wind_direction = 0.0
wind_speed = 15.0

# Heading 180° (south, toward goal)
heading = 180
wind_angle = calculate_wind_angle(heading, wind_direction)
boat_speed = get_boat_speed(wind_speed, wind_angle, 'sailboat')

logger.info(f"Test heading: {heading}deg (toward goal)")
logger.info(f"Wind from: {wind_direction}deg at {wind_speed}kt")
logger.info(f"Wind angle: {wind_angle}deg")
logger.info(f"Boat speed: {boat_speed}kt")
logger.info()

# Calculate new position after 1 hour
distance_nm = boat_speed * 1.0  # 1 hour
new_position = calculate_destination(start, distance_nm, heading)
new_distance_to_goal = calculate_distance(new_position, end)

logger.info(f"After 1 hour at heading {heading}:")
logger.info(f"  New position: {new_position.lat:.3f}N, {new_position.lng:.3f}E")
logger.info(f"  Distance traveled: {distance_nm:.1f}nm")
logger.info(f"  New distance to goal: {new_distance_to_goal:.1f}nm")
logger.info(f"  Progress made: {30.0 - new_distance_to_goal:.1f}nm closer!")
logger.info()

# Create the point
new_point = IsochronePoint(
    position=new_position,
    time_hours=1.0,
    parent=None,
    heading=heading,
    accumulated_distance=distance_nm
)

# Check if it would be pruned
cell = get_grid_cell(new_position, GRID_CELL_SIZE)
logger.info(f"Grid cell: {cell}")
logger.info(f"Cell in visited_grid? {cell in state.visited_grid}")
logger.info()

# Test pruning
logger.info("Testing pruning logic...")
should_prune = should_prune_point(new_point, state, end)
logger.info(f"  Result: {'PRUNED' if should_prune else 'KEPT'}")
logger.info()

if not should_prune:
    logger.info("SUCCESS: Point would be kept!")
    logger.info(f"Closest distance should update to: {new_distance_to_goal:.1f}nm")
else:
    logger.info("PROBLEM: Point is being pruned even though it makes progress!")

