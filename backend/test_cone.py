"""Test directional cone logic for route planning"""

import logging
from isochrone_router import is_in_directional_cone

logger = logging.getLogger(__name__)


def test_directional_cone_south():
    """Test directional cone when heading south (180°)"""
    destination_bearing = 180  # South
    distance_to_goal = 30
    
    # Headings within the cone (roughly south) should be allowed
    # Headings pointing away from destination should be skipped
    
    # Test cases: (heading, expected_result, description)
    test_cases = [
        (180, True, "Direct south - should be allowed"),
        (135, True, "Southeast - should be allowed"),
        (225, True, "Southwest - should be allowed"),
        (90, False, "East - perpendicular, should be skipped when far from goal"),
        (270, False, "West - perpendicular, should be skipped when far from goal"),
        (0, False, "North - opposite direction, should be skipped"),
    ]
    
    for heading, expected, description in test_cases:
        result = is_in_directional_cone(heading, destination_bearing, distance_to_goal)
        logger.info(f"Heading {heading:3d}° ({description}): {'PASS' if result == expected else 'FAIL'}")
        assert result == expected, f"Failed: {description}"


def test_directional_cone_near_goal():
    """Test that cone widens when near the goal"""
    destination_bearing = 180  # South
    close_distance = 5  # Close to goal
    
    # When close to goal, more headings should be allowed
    # Even perpendicular headings might be acceptable
    heading = 90  # East (perpendicular)
    
    result = is_in_directional_cone(heading, destination_bearing, close_distance)
    # This should be allowed when close (cone is wider)
    logger.info(f"Perpendicular heading when close ({close_distance}nm): {'ALLOWED' if result else 'SKIPPED'}")
    assert result == True, "Perpendicular heading should be allowed when close to goal"


def test_directional_cone_all_headings_south():
    """Test all major compass headings for south-bound route"""
    destination_bearing = 180  # South
    distance_to_goal = 30
    
    test_headings = [0, 45, 90, 135, 180, 225, 270, 315]
    results = {}
    
    for heading in test_headings:
        result = is_in_directional_cone(heading, destination_bearing, distance_to_goal)
        results[heading] = result
        logger.info(f"  Heading {heading:3d}° = {'ALLOWED' if result else 'SKIPPED'}")
    
    # Verify that at least the direct heading (180) is allowed
    assert results[180] == True, "Direct heading to goal must be allowed"
    
    # Verify that opposite heading (0) is skipped
    assert results[0] == False, "Opposite heading should be skipped"

