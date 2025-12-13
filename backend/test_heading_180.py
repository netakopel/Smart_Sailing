"""
Test isochrone pruning logic - ensure heading 180° makes progress
"""

import logging
from models import Coordinates
from isochrone_router import (
    IsochronePoint, IsochroneState, should_prune_point,
    get_grid_cell, GRID_CELL_SIZE
)
from route_generator import calculate_distance, calculate_destination
from polars import get_boat_speed, calculate_wind_angle

logger = logging.getLogger(__name__)


def test_heading_180_not_pruned():
    """Test that heading 180° (directly toward goal) is not pruned"""
    # Setup: Sailing south from 50.5N to 50.0N
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    # Initial state
    state = IsochroneState()
    state.closest_distance_to_goal = calculate_distance(start, end)
    
    # Wind from north (0°) - favorable for southbound
    wind_direction = 0.0
    wind_speed = 15.0
    
    # Heading 180° (south, directly toward goal)
    heading = 180
    wind_angle = calculate_wind_angle(heading, wind_direction)
    boat_speed = get_boat_speed(wind_speed, wind_angle, 'sailboat')
    
    logger.info(f"Boat speed at heading {heading}° with {wind_speed}kt wind: {boat_speed}kt")
    
    # Calculate new position after 1 hour
    distance_nm = boat_speed * 1.0  # 1 hour
    new_position = calculate_destination(start, distance_nm, heading)
    new_distance_to_goal = calculate_distance(new_position, end)
    
    # Create the isochrone point
    new_point = IsochronePoint(
        position=new_position,
        time_hours=1.0,
        parent=None,
        heading=heading,
        accumulated_distance=distance_nm
    )
    
    # Test that it's not pruned
    should_prune = should_prune_point(new_point, state, end)
    
    logger.info(f"Progress made: {state.closest_distance_to_goal - new_distance_to_goal:.1f}nm closer")
    logger.info(f"Point {'PRUNED' if should_prune else 'KEPT'}")
    
    assert not should_prune, "Heading directly toward goal should not be pruned"
    assert new_distance_to_goal < state.closest_distance_to_goal, "Should make progress toward goal"


def test_heading_makes_progress():
    """Test that isochrone points making progress are kept"""
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    initial_distance = calculate_distance(start, end)
    state = IsochroneState()
    state.closest_distance_to_goal = initial_distance
    
    # Test multiple headings that should make progress
    headings_to_test = [
        (180, "Direct south"),
        (170, "Slightly east of south"),
        (190, "Slightly west of south"),
    ]
    
    for heading, description in headings_to_test:
        wind_angle = calculate_wind_angle(heading, 0.0)  # North wind
        boat_speed = get_boat_speed(15.0, wind_angle, 'sailboat')
        
        if boat_speed > 0:  # Only test if boat can move
            new_position = calculate_destination(start, boat_speed, heading)
            new_distance = calculate_distance(new_position, end)
            
            new_point = IsochronePoint(
                position=new_position,
                time_hours=1.0,
                parent=None,
                heading=heading,
                accumulated_distance=boat_speed
            )
            
            should_prune = should_prune_point(new_point, state, end)
            progress = initial_distance - new_distance
            
            logger.info(f"{description} ({heading}°): Progress={progress:.2f}nm, {'KEPT' if not should_prune else 'PRUNED'}")
            
            if progress > 0.1:  # If making significant progress
                assert not should_prune, f"{description} making progress should not be pruned"


def test_grid_cell_assignment():
    """Test that grid cells are assigned correctly"""
    position1 = Coordinates(lat=50.5, lng=-1.0)
    position2 = Coordinates(lat=50.5, lng=-1.0)  # Same position
    position3 = Coordinates(lat=51.0, lng=-1.0)  # Different position
    
    cell1 = get_grid_cell(position1, GRID_CELL_SIZE)
    cell2 = get_grid_cell(position2, GRID_CELL_SIZE)
    cell3 = get_grid_cell(position3, GRID_CELL_SIZE)
    
    logger.info(f"Cell 1: {cell1}")
    logger.info(f"Cell 2: {cell2}")
    logger.info(f"Cell 3: {cell3}")
    
    assert cell1 == cell2, "Same position should have same grid cell"
    assert cell1 != cell3, "Different positions should have different grid cells"

