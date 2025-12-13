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


def test_pruning_prevents_revisiting_cells():
    """Test that pruning prevents revisiting already-visited grid cells"""
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    state = IsochroneState()
    state.closest_distance_to_goal = 30.0
    
    # Create a point and add it to visited grid
    first_point = IsochronePoint(
        position=Coordinates(lat=50.4, lng=-1.0),
        time_hours=1.0,
        parent=None,
        accumulated_distance=8.0
    )
    
    cell = get_grid_cell(first_point.position, GRID_CELL_SIZE)
    state.visited_grid[cell] = first_point.time_hours
    
    # Try to visit the same cell again with slower time
    second_point = IsochronePoint(
        position=Coordinates(lat=50.4, lng=-1.0),  # Same position
        time_hours=2.0,  # Slower
        parent=None,
        accumulated_distance=10.0
    )
    
    should_prune = should_prune_point(second_point, state, end)
    
    logger.info(f"First visit time: {first_point.time_hours}h")
    logger.info(f"Second visit time: {second_point.time_hours}h")
    logger.info(f"Second point {'PRUNED' if should_prune else 'KEPT'}")
    
    assert should_prune, "Slower visit to same grid cell should be pruned"


def test_pruning_keeps_faster_arrival():
    """Test that faster arrivals to a cell are kept"""
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    state = IsochroneState()
    state.closest_distance_to_goal = 30.0
    
    position = Coordinates(lat=50.4, lng=-1.0)
    cell = get_grid_cell(position, GRID_CELL_SIZE)
    
    # First visit at 2.0 hours
    state.visited_grid[cell] = 2.0
    
    # Second visit at 1.0 hours (faster!)
    faster_point = IsochronePoint(
        position=position,
        time_hours=1.0,
        parent=None,
        accumulated_distance=8.0
    )
    
    should_prune = should_prune_point(faster_point, state, end)
    
    logger.info(f"Previous arrival: 2.0h")
    logger.info(f"New faster arrival: 1.0h")
    logger.info(f"Faster point {'PRUNED' if should_prune else 'KEPT'}")
    
    assert not should_prune, "Faster arrival should not be pruned"


def test_pruning_with_multiple_propagation_points():
    """Test pruning behavior with multiple propagation fronts"""
    import math
    
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    state = IsochroneState()
    state.closest_distance_to_goal = 30.0
    
    # Simulate 5 points from first propagation
    sample_points = [
        IsochronePoint(Coordinates(lat=50.6, lng=-1.1), time_hours=1.0, accumulated_distance=8.0),  # NW
        IsochronePoint(Coordinates(lat=50.6, lng=-0.9), time_hours=1.0, accumulated_distance=8.0),  # NE
        IsochronePoint(Coordinates(lat=50.5, lng=-1.2), time_hours=1.0, accumulated_distance=9.0),  # W
        IsochronePoint(Coordinates(lat=50.5, lng=-0.8), time_hours=1.0, accumulated_distance=9.0),  # E
        IsochronePoint(Coordinates(lat=50.4, lng=-1.0), time_hours=1.0, accumulated_distance=7.0),  # S (closest)
    ]
    
    # Add all to visited grid
    for pt in sample_points:
        cell = get_grid_cell(pt.position, GRID_CELL_SIZE)
        state.visited_grid[cell] = pt.time_hours
    
    logger.info(f"Visited grid has {len(state.visited_grid)} cells after first propagation")
    
    # Propagate from the southern point (closest to goal)
    current_point = sample_points[4]
    
    # Try heading 180° (directly south)
    heading = 180
    distance = 8.0  # nm
    lat_change = (distance / 60) * math.cos(math.radians(heading))
    lng_change = (distance / 60) * math.sin(math.radians(heading)) / math.cos(math.radians(current_point.position.lat))
    
    new_point = IsochronePoint(
        position=Coordinates(
            lat=current_point.position.lat + lat_change,
            lng=current_point.position.lng + lng_change
        ),
        time_hours=2.0,
        parent=current_point,
        accumulated_distance=current_point.accumulated_distance + distance
    )
    
    dist_to_goal = calculate_distance(new_point.position, end)
    new_cell = get_grid_cell(new_point.position, GRID_CELL_SIZE)
    
    # This should be a new cell (not visited yet)
    is_new_cell = new_cell not in state.visited_grid
    should_prune = should_prune_point(new_point, state, end)
    
    logger.info(f"New cell: {new_cell}")
    logger.info(f"Is new cell? {is_new_cell}")
    logger.info(f"Distance to goal: {dist_to_goal:.1f}nm")
    logger.info(f"Point {'PRUNED' if should_prune else 'KEPT'}")
    
    if is_new_cell:
        assert not should_prune, "New unexplored cell should not be pruned"

