"""
Test if heading 180° is actually being added to the first isochrone
"""

from datetime import datetime, timezone, timedelta
from models import Coordinates, WaypointWeather
from isochrone_router import (
    IsochronePoint, IsochroneState, should_prune_point,
    get_grid_cell, GRID_CELL_SIZE
)
from route_generator import calculate_distance, calculate_destination
from polars import get_boat_speed, calculate_wind_angle

print("="*70)
print("TEST: Why isn't heading 180deg making progress?")
print("="*70)

start = Coordinates(lat=50.5, lng=-1.0)
end = Coordinates(lat=50.0, lng=-1.0)

print(f"\nStart: {start.lat}N, {start.lng}E")
print(f"End: {end.lat}N, {end.lng}E")
print(f"Distance: {calculate_distance(start, end):.1f}nm")
print()

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

print(f"Test heading: {heading}deg (toward goal)")
print(f"Wind from: {wind_direction}deg at {wind_speed}kt")
print(f"Wind angle: {wind_angle}deg")
print(f"Boat speed: {boat_speed}kt")
print()

# Calculate new position after 1 hour
distance_nm = boat_speed * 1.0  # 1 hour
new_position = calculate_destination(start, distance_nm, heading)
new_distance_to_goal = calculate_distance(new_position, end)

print(f"After 1 hour at heading {heading}:")
print(f"  New position: {new_position.lat:.3f}N, {new_position.lng:.3f}E")
print(f"  Distance traveled: {distance_nm:.1f}nm")
print(f"  New distance to goal: {new_distance_to_goal:.1f}nm")
print(f"  Progress made: {30.0 - new_distance_to_goal:.1f}nm closer!")
print()

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
print(f"Grid cell: {cell}")
print(f"Cell in visited_grid? {cell in state.visited_grid}")
print()

# Test pruning
print("Testing pruning logic...")
should_prune = should_prune_point(new_point, state, end)
print(f"  Result: {'PRUNED' if should_prune else 'KEPT'}")
print()

if not should_prune:
    print("SUCCESS: Point would be kept!")
    print(f"Closest distance should update to: {new_distance_to_goal:.1f}nm")
else:
    print("PROBLEM: Point is being pruned even though it makes progress!")

