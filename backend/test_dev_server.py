"""
Test script for dev_server.py

This script sends requests to the local dev server to test different algorithms.

Usage:
    1. In one terminal: python dev_server.py
    2. In another terminal: python test_dev_server.py
"""

import requests
import json
import logging
from datetime import datetime, timedelta

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dev server URL
BASE_URL = "http://localhost:8000"

def test_algorithm(algorithm_name, start, end, boat_type="sailboat"):
    """
    Test a specific routing algorithm.
    
    Args:
        algorithm_name: 'naive', 'hybrid', 'isochrone', or 'all'
        start: {"lat": float, "lng": float}
        end: {"lat": float, "lng": float}
        boat_type: 'sailboat', 'motorboat', or 'catamaran'
    """
    logger.info(f"\n{'='*70}")
    logger.info(f"Testing Algorithm: {algorithm_name.upper()}")
    logger.info(f"{'='*70}")
    
    # Prepare request
    departure = (datetime.now() + timedelta(hours=2)).isoformat()
    
    payload = {
        "start": start,
        "end": end,
        "boat_type": boat_type,
        "departure_time": departure,
        "algorithm": algorithm_name
    }
    
    logger.info(f"\nRequest:")
    logger.info(f"  From: {start['lat']:.4f}, {start['lng']:.4f}")
    logger.info(f"  To: {end['lat']:.4f}, {end['lng']:.4f}")
    logger.info(f"  Boat: {boat_type}")
    logger.info(f"  Algorithm: {algorithm_name}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/calculate-routes",
            json=payload,
            timeout=120  # 2 minute timeout for isochrone
        )
        
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])
            
            logger.info(f"\n✓ Success! Got {len(routes)} routes")
            logger.info(f"\nResults:")
            for i, route in enumerate(routes, 1):
                logger.info(f"\n  {i}. {route['name']}")
                logger.info(f"     Score: {route['score']}/100")
                logger.info(f"     Distance: {route['distance']:.1f} nm")
                logger.info(f"     Time: {route['estimatedTime']}")
                logger.info(f"     Waypoints: {len(route['waypoints'])}")
        else:
            logger.info(f"\n✗ Error {response.status_code}")
            logger.info(response.text)
            
    except requests.exceptions.ConnectionError:
        logger.info("\n✗ Error: Cannot connect to dev server!")
        logger.info("  Make sure dev_server.py is running:")
        logger.info("  python backend/dev_server.py")
    except requests.exceptions.Timeout:
        logger.info("\n✗ Error: Request timed out (took > 2 minutes)")
    except Exception as e:
        logger.info(f"\n✗ Error: {e}")


def main():
    logger.info("\n" + "="*70)
    logger.info("  ISOCHRONE ALGORITHM - LOCAL TEST")
    logger.info("="*70)
    
    # Test route: Short distance for quick testing
    # Southampton to Isle of Wight (about 15nm)
    start = {"lat": 50.9, "lng": -1.4}  # Southampton
    end = {"lat": 50.7, "lng": -1.3}    # Isle of Wight
    
    logger.info("\nTest Route: Southampton → Isle of Wight (~15nm)")
    
    # Test 1: Naive algorithm (baseline)
    logger.info("\n" + "-"*70)
    logger.info("TEST 1: NAIVE ALGORITHM (baseline)")
    test_algorithm("naive", start, end)
    
    # Test 2: Isochrone algorithm (the new one!)
    logger.info("\n" + "-"*70)
    logger.info("TEST 2: ISOCHRONE ALGORITHM (optimal)")
    test_algorithm("isochrone", start, end)
    
    # Test 3: Compare all
    logger.info("\n" + "-"*70)
    logger.info("TEST 3: ALL ALGORITHMS (comparison)")
    test_algorithm("all", start, end)
    
    logger.info("\n" + "="*70)
    logger.info("  TESTS COMPLETE")
    logger.info("="*70)
    logger.info("\nNext steps:")
    logger.info("  1. Check the terminal running dev_server.py for detailed logs")
    logger.info("  2. Open frontend at http://localhost:5173 to see routes on map")
    logger.info("  3. Try different start/end points in this script")
    logger.info()


if __name__ == "__main__":
    main()

