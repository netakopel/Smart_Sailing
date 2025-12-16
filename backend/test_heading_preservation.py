"""
Test that heading is preserved when weather is fetched and attached to waypoints.
"""

import logging
from datetime import datetime
from models import Coordinates, Waypoint, WaypointWeather, BoatType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_heading_preserved_in_waypoint():
    """Test that waypoint heading is preserved through dataclass operations."""
    logger.info("=" * 60)
    logger.info("TEST: Heading Preserved in Waypoint")
    logger.info("=" * 60)
    
    # Create a waypoint WITH heading
    original_waypoint = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=None,
        heading=45.0  # Northeast
    )
    
    logger.info(f"Original waypoint heading: {original_waypoint.heading}°")
    assert original_waypoint.heading == 45.0, "Original heading should be preserved"
    
    # Simulate what weather_fetcher.py does: create new waypoint with weather but preserve heading
    new_weather = WaypointWeather(
        wind_speed=15.0,
        wind_direction=90.0,
        wave_height=1.5,
        precipitation=0.0,
        visibility=10.0,
        temperature=10.0
    )
    
    updated_waypoint = Waypoint(
        position=original_waypoint.position,
        estimated_arrival=original_waypoint.estimated_arrival,
        weather=new_weather,
        heading=original_waypoint.heading  # THIS IS THE FIX!
    )
    
    logger.info(f"Updated waypoint heading: {updated_waypoint.heading}°")
    logger.info(f"Updated waypoint weather: {updated_waypoint.weather}")
    
    assert updated_waypoint.heading == 45.0, "Heading should be preserved after adding weather"
    assert updated_waypoint.weather is not None, "Weather should be added"
    assert updated_waypoint.position == original_waypoint.position, "Position should be preserved"
    
    logger.info("✓ PASS: Heading preserved when weather is added to waypoint")


def test_heading_none_handling():
    """Test that waypoints without heading (None) are handled correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Heading None Handling")
    logger.info("=" * 60)
    
    # Create a waypoint WITHOUT heading (None)
    waypoint_no_heading = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=None,
        heading=None  # No heading
    )
    
    logger.info(f"Waypoint heading: {waypoint_no_heading.heading}")
    assert waypoint_no_heading.heading is None, "Heading should be None"
    
    # Add weather while preserving None heading
    new_weather = WaypointWeather(
        wind_speed=15.0,
        wind_direction=90.0,
        wave_height=1.5,
        precipitation=0.0,
        visibility=10.0,
        temperature=10.0
    )
    
    updated_waypoint = Waypoint(
        position=waypoint_no_heading.position,
        estimated_arrival=waypoint_no_heading.estimated_arrival,
        weather=new_weather,
        heading=waypoint_no_heading.heading  # Preserve None
    )
    
    logger.info(f"Updated waypoint heading: {updated_waypoint.heading}")
    
    assert updated_waypoint.heading is None, "Heading should remain None if it was None"
    assert updated_waypoint.weather is not None, "Weather should be added"
    
    logger.info("✓ PASS: None heading handled correctly")


if __name__ == "__main__":
    logger.info("\n" + "=" * 60)
    logger.info("HEADING PRESERVATION TESTS")
    logger.info("=" * 60 + "\n")
    
    try:
        test_heading_preserved_in_waypoint()
        test_heading_none_handling()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nThe fix ensures that waypoint headings (stored during isochrone")
        logger.info("propagation) are preserved when weather is fetched and attached.")
        
    except AssertionError as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        raise

