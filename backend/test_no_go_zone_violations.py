"""
Test for no-go zone violation detection fix.

Verifies that waypoint headings stored during isochrone propagation are used
correctly when calculating no-go zone violations for frontend display.
"""

import logging
from models import Coordinates, Waypoint, WaypointWeather, BoatType
from polars import calculate_wind_angle, is_in_no_go_zone

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_no_go_zone_detection_with_stored_heading():
    """
    Test that no-go zone violations are correctly detected using stored heading.
    
    This test verifies the fix where:
    1. Waypoint has a stored heading (from isochrone propagation)
    2. We use this stored heading to calculate wind angle
    3. We check if wind angle puts us in no-go zone
    """
    logger.info("=" * 60)
    logger.info("TEST: No-Go Zone Detection with Stored Heading")
    logger.info("=" * 60)
    
    # Create a waypoint with stored heading sailing upwind (in no-go zone)
    # Boat heading 0° (north), wind from 0° (north) = 0° wind angle (headwind, in no-go zone)
    waypoint = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=WaypointWeather(
            wind_speed=15.0,
            wind_direction=0.0,  # Wind from north
            wave_height=1.5,
            precipitation=0.0,
            visibility=10.0,
            temperature=10.0
        ),
        heading=0.0  # Sailing north (INTO the wind - no-go zone!)
    )
    
    # Calculate wind angle using stored heading
    wind_angle = calculate_wind_angle(waypoint.heading, waypoint.weather.wind_direction)
    
    logger.info(f"Waypoint heading: {waypoint.heading:.1f}°")
    logger.info(f"Wind direction: {waypoint.weather.wind_direction:.1f}°")
    logger.info(f"Calculated wind angle: {wind_angle:.1f}°")
    
    # Check if in no-go zone
    in_no_go = is_in_no_go_zone(wind_angle, BoatType.SAILBOAT.value)
    
    logger.info(f"In no-go zone (sailboat): {in_no_go}")
    
    assert in_no_go, "Should be in no-go zone when sailing directly into wind"
    logger.info("✓ PASS: Correctly identified no-go zone violation")
    

def test_no_go_zone_not_triggered_on_beam_reach():
    """
    Test that no-go zone is NOT triggered on a beam reach (valid sailing angle).
    """
    logger.info("\n" + "=" * 60)
    logger.info("TEST: No-Go Zone NOT Triggered on Beam Reach")
    logger.info("=" * 60)
    
    # Create a waypoint sailing perpendicular to wind (beam reach)
    # Boat heading 0° (north), wind from 90° (east) = 90° wind angle (beam reach, VALID)
    waypoint = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=WaypointWeather(
            wind_speed=15.0,
            wind_direction=90.0,  # Wind from east
            wave_height=1.5,
            precipitation=0.0,
            visibility=10.0,
            temperature=10.0
        ),
        heading=0.0  # Sailing north (PERPENDICULAR to wind - beam reach)
    )
    
    # Calculate wind angle using stored heading
    wind_angle = calculate_wind_angle(waypoint.heading, waypoint.weather.wind_direction)
    
    logger.info(f"Waypoint heading: {waypoint.heading:.1f}°")
    logger.info(f"Wind direction: {waypoint.weather.wind_direction:.1f}°")
    logger.info(f"Calculated wind angle: {wind_angle:.1f}°")
    
    # Check if in no-go zone
    in_no_go = is_in_no_go_zone(wind_angle, BoatType.SAILBOAT.value)
    
    logger.info(f"In no-go zone (sailboat): {in_no_go}")
    
    assert not in_no_go, "Should NOT be in no-go zone on beam reach"
    logger.info("✓ PASS: Correctly identified valid sailing angle (beam reach)")


def test_no_go_zone_borderline_close_hauled():
    """
    Test behavior at the borderline of no-go zone (close-hauled).
    
    At ~50° wind angle, we're just outside the no-go zone (which is < 45°).
    """
    logger.info("\n" + "=" * 60)
    logger.info("TEST: No-Go Zone Borderline (Close-Hauled)")
    logger.info("=" * 60)
    
    # Close-hauled just outside no-go zone
    # Boat heading 50° (NE), wind from 0° (north) = 50° wind angle
    waypoint = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=WaypointWeather(
            wind_speed=15.0,
            wind_direction=0.0,  # Wind from north
            wave_height=1.5,
            precipitation=0.0,
            visibility=10.0,
            temperature=10.0
        ),
        heading=50.0  # Sailing NE at 50° wind angle (just outside no-go zone)
    )
    
    # Calculate wind angle
    wind_angle = calculate_wind_angle(waypoint.heading, waypoint.weather.wind_direction)
    
    logger.info(f"Waypoint heading: {waypoint.heading:.1f}°")
    logger.info(f"Wind direction: {waypoint.weather.wind_direction:.1f}°")
    logger.info(f"Calculated wind angle: {wind_angle:.1f}°")
    
    # Check if in no-go zone
    in_no_go = is_in_no_go_zone(wind_angle, BoatType.SAILBOAT.value)
    
    logger.info(f"In no-go zone (sailboat): {in_no_go}")
    
    # At 50°, should NOT be in no-go zone (threshold is 45°)
    assert not in_no_go, "50° wind angle should be just outside no-go zone"
    logger.info("✓ PASS: Correctly identified as valid close-hauled angle")


def test_motorboat_no_no_go_zone():
    """
    Test that motorboats never have no-go zone violations.
    """
    logger.info("\n" + "=" * 60)
    logger.info("TEST: Motorboat Has No No-Go Zone")
    logger.info("=" * 60)
    
    # Even sailing directly into wind, motorboat should be fine
    waypoint = Waypoint(
        position=Coordinates(lat=50.0, lng=-2.0),
        estimated_arrival="2024-01-15T10:00:00Z",
        weather=WaypointWeather(
            wind_speed=15.0,
            wind_direction=0.0,  # Wind from north
            wave_height=1.5,
            precipitation=0.0,
            visibility=10.0,
            temperature=10.0
        ),
        heading=0.0  # Sailing north (into wind)
    )
    
    # Calculate wind angle
    wind_angle = calculate_wind_angle(waypoint.heading, waypoint.weather.wind_direction)
    
    logger.info(f"Waypoint heading: {waypoint.heading:.1f}°")
    logger.info(f"Wind direction: {waypoint.weather.wind_direction:.1f}°")
    logger.info(f"Calculated wind angle: {wind_angle:.1f}°")
    
    # Check if motorboat is in no-go zone
    in_no_go_sailboat = is_in_no_go_zone(wind_angle, BoatType.SAILBOAT.value)
    in_no_go_motorboat = is_in_no_go_zone(wind_angle, BoatType.MOTORBOAT.value)
    
    logger.info(f"In no-go zone (sailboat): {in_no_go_sailboat}")
    logger.info(f"In no-go zone (motorboat): {in_no_go_motorboat}")
    
    assert in_no_go_sailboat, "Sailboat should be in no-go zone at 0° wind angle"
    assert not in_no_go_motorboat, "Motorboat should never be in no-go zone"
    logger.info("✓ PASS: Motorboat correctly identified as having no no-go zone")


if __name__ == "__main__":
    logger.info("\n" + "=" * 60)
    logger.info("NO-GO ZONE VIOLATION DETECTION TESTS")
    logger.info("=" * 60 + "\n")
    
    try:
        test_no_go_zone_detection_with_stored_heading()
        test_no_go_zone_not_triggered_on_beam_reach()
        test_no_go_zone_borderline_close_hauled()
        test_motorboat_no_no_go_zone()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        
    except AssertionError as e:
        logger.error(f"\n✗ TEST FAILED: {e}")
        raise

