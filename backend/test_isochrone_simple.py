"""
Simple test for isochrone router using mock weather data.

This avoids the API call issue and allows us to test the core algorithm.
"""

from datetime import datetime, timedelta, timezone
from models import RouteRequest, Coordinates, BoatType, WaypointWeather
from isochrone_router import calculate_isochrone_route
from route_generator import calculate_distance

# Create mock weather grid with uniform conditions
def create_mock_weather_grid(start, end, wind_direction=0.0):
    """Create a simple weather grid with uniform wind.
    
    Args:
        start: Starting coordinates
        end: Ending coordinates
        wind_direction: Wind direction in degrees (default 0.0 = from north)
    """
    
    # Create grid points (3x3 grid covering route area)
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
    
    # Create times (24 hours of forecast, hourly) - timezone-aware
    base_time = datetime(2024, 1, 15, 8, 0, 0, tzinfo=timezone.utc)
    times = [base_time + timedelta(hours=h) for h in range(24)]
    
    # Create uniform weather at all grid points and times
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


def test_simple_route():
    """Test with a short route."""
    print("\n" + "="*60)
    print("SIMPLE ISOCHRONE TEST")
    print("="*60)
    
    # Very short route: 30nm south (with headwind) - easier test
    start = Coordinates(lat=50.5, lng=-1.0)
    end = Coordinates(lat=50.0, lng=-1.0)
    
    distance = calculate_distance(start, end)
    print(f"\nRoute: ({start.lat}, {start.lng}) -> ({end.lat}, {end.lng})")
    print(f"Distance: {distance:.1f} nm")
    print(f"Wind: 15kt from North (headwind scenario)")
    
    request = RouteRequest(
        start=start,
        end=end,
        boat_type=BoatType.SAILBOAT,
        departure_time="2024-01-15T08:00:00Z"
    )
    
    # Create mock weather
    weather_grid = create_mock_weather_grid(start, end)
    
    # Calculate route
    route = calculate_isochrone_route(request, weather_grid, max_time_hours=24.0)
    
    if route:
        print(f"\n[SUCCESS] Route found!")
        print(f"  Time: {route.estimated_hours:.1f} hours")
        print(f"  Distance: {route.distance:.1f} nm")
        print(f"  Waypoints: {len(route.waypoints)}")
        print(f"  Speed: {route.distance / route.estimated_hours:.1f} knots")
        return True
    else:
        print(f"\n[FAILED] No route found")
        return False


def test_beam_reach():
    """Test with favorable beam reach conditions."""
    print("\n" + "="*60)
    print("BEAM REACH TEST")
    print("="*60)
    
    # Short route going north with wind from east (beam reach)
    start = Coordinates(lat=50.0, lng=-1.0)
    end = Coordinates(lat=50.5, lng=-1.0)
    
    distance = calculate_distance(start, end)
    print(f"\nRoute: ({start.lat}, {start.lng}) -> ({end.lat}, {end.lng})")
    print(f"Distance: {distance:.1f} nm")
    print(f"Wind: 15kt from East (beam reach - fast!)")
    
    request = RouteRequest(
        start=start,
        end=end,
        boat_type=BoatType.SAILBOAT,
        departure_time="2024-01-15T08:00:00Z"
    )
    
    # Create weather grid with wind from east (beam reach)
    weather_grid = create_mock_weather_grid(start, end, wind_direction=90.0)
    
    # Calculate route
    route = calculate_isochrone_route(request, weather_grid, max_time_hours=24.0)
    
    if route:
        print(f"\n[SUCCESS] Route found!")
        print(f"  Time: {route.estimated_hours:.1f} hours")
        print(f"  Distance: {route.distance:.1f} nm")
        print(f"  Waypoints: {len(route.waypoints)}")
        print(f"  Speed: {route.distance / route.estimated_hours:.1f} knots")
        return True
    else:
        print(f"\n[FAILED] No route found")
        return False


if __name__ == "__main__":
    print("Testing Isochrone Router with Mock Weather Data")
    print("="*60)
    
    # Test 1: Simple headwind scenario
    test1_passed = test_simple_route()
    
    # Test 2: Favorable beam reach
    test2_passed = test_beam_reach()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Simple Route (Headwind): {'PASSED' if test1_passed else 'FAILED'}")
    print(f"Beam Reach (Favorable): {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\n[SUCCESS] All tests passed!")
    else:
        print("\n[FAILED] Some tests failed")

