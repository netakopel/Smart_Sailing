"""
Test land detection functionality
"""
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from models import Coordinates
from land_detector import is_land, is_water, is_close_to_land, LAND_DETECTION_AVAILABLE

def test_land_detection():
    """Test basic land detection"""
    print("="*60)
    print("Testing Land Detection")
    print("="*60)
    
    if not LAND_DETECTION_AVAILABLE:
        print("ERROR: global-land-mask package not available!")
        print("Install with: pip install global-land-mask")
        return False
    
    print("✓ global-land-mask package is available")
    print()
    
    # Test cases: (name, lat, lng, expected_is_land)
    test_cases = [
        # Water locations
        ("Atlantic Ocean (mid)", 40.0, -30.0, False),
        ("Mediterranean Sea", 36.0, 15.0, False),
        ("Pacific Ocean", 0.0, -150.0, False),
        
        # Land locations
        ("Paris, France", 48.8566, 2.3522, True),
        ("New York, USA", 40.7128, -74.0060, True),
        ("Tokyo, Japan", 35.6762, 139.6503, True),
        
        # Coastal locations (should be water but close to land)
        ("Off coast of Spain", 36.5, -6.0, False),
        ("Off coast of Italy", 40.0, 14.0, False),
    ]
    
    print("Testing specific locations:")
    print("-" * 60)
    
    all_passed = True
    for name, lat, lng, expected_is_land in test_cases:
        pos = Coordinates(lat=lat, lng=lng)
        result = is_land(pos)
        status = "✓" if result == expected_is_land else "✗"
        
        if result != expected_is_land:
            all_passed = False
            
        print(f"{status} {name:30s} ({lat:7.3f}, {lng:8.3f}): "
              f"{'LAND' if result else 'WATER':5s} "
              f"(expected: {'LAND' if expected_is_land else 'WATER'})")
    
    print()
    print("="*60)
    
    # Test close to land detection
    print("\nTesting 'close to land' detection:")
    print("-" * 60)
    
    # Test a point in the Atlantic (should not be close to land)
    atlantic_point = Coordinates(lat=40.0, lng=-30.0)
    is_close = is_close_to_land(atlantic_point, buffer_distance_nm=3.0)
    print(f"Atlantic Ocean (40.0, -30.0): {'CLOSE TO LAND' if is_close else 'NOT CLOSE TO LAND'}")
    print(f"  Expected: NOT CLOSE TO LAND")
    print(f"  Result: {'✓' if not is_close else '✗'}")
    
    # Test a point near the coast of Spain (should be close to land)
    spain_coast = Coordinates(lat=36.5, lng=-6.0)
    is_close = is_close_to_land(spain_coast, buffer_distance_nm=10.0)
    print(f"\nOff coast of Spain (36.5, -6.0): {'CLOSE TO LAND' if is_close else 'NOT CLOSE TO LAND'}")
    print(f"  Expected: CLOSE TO LAND (within 10nm)")
    print(f"  Result: {'✓' if is_close else '✗'}")
    
    print()
    print("="*60)
    
    if all_passed:
        print("✓ All land detection tests passed!")
    else:
        print("✗ Some tests failed - check results above")
    
    return all_passed


if __name__ == "__main__":
    test_land_detection()

