"""
Test script to check if weather API is accessible and not blocked.

Run this to diagnose API issues:
    python backend/test_weather_api.py
"""

import sys
import logging
from weather_fetcher import MARINE_API_URL, WEATHER_APIS
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_single_api_call():
    """Test a single API call to see if it works."""
    logger.info("=" * 60)
    logger.info("Testing Weather API Access")
    logger.info("=" * 60)
    
    # Test weather API
    logger.info("\n1. Testing Weather API (Open-Meteo)...")
    try:
        response = requests.get(WEATHER_APIS['default'], params={
            'latitude': '40.0',
            'longitude': '-70.0',
            'hourly': 'wind_speed_10m,wind_direction_10m',
            'forecast_days': 1
        }, timeout=10)
        
        logger.info(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("   ✓ Weather API is working!")
            data = response.json()
            logger.info(f"   Response keys: {list(data.keys())}")
        elif response.status_code == 429:
            logger.error("   ✗ RATE LIMIT EXCEEDED - You are being rate-limited!")
            logger.error("   Wait a few minutes and try again.")
            return False
        elif response.status_code == 403:
            logger.error("   ✗ ACCESS FORBIDDEN - You may be blocked!")
            logger.error("   Your IP or API key may be blocked.")
            return False
        else:
            logger.warning(f"   ⚠ Unexpected status: {response.status_code}")
            logger.warning(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"   ✗ Error: {e}")
        return False
    
    # Test marine API
    logger.info("\n2. Testing Marine API (Open-Meteo Marine)...")
    try:
        response = requests.get(MARINE_API_URL, params={
            'latitude': '40.0',
            'longitude': '-70.0',
            'hourly': 'wave_height',
            'forecast_days': 1
        }, timeout=10)
        
        logger.info(f"   Status Code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("   ✓ Marine API is working!")
            data = response.json()
            logger.info(f"   Response keys: {list(data.keys())}")
        elif response.status_code == 429:
            logger.error("   ✗ RATE LIMIT EXCEEDED - You are being rate-limited!")
            logger.error("   Wait a few minutes and try again.")
            return False
        elif response.status_code == 403:
            logger.error("   ✗ ACCESS FORBIDDEN - You may be blocked!")
            logger.error("   Your IP or API key may be blocked.")
            return False
        else:
            logger.warning(f"   ⚠ Unexpected status: {response.status_code}")
            logger.warning(f"   Response: {response.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"   ✗ Error: {e}")
        return False
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ All API tests passed! Weather API is accessible.")
    logger.info("=" * 60)
    return True

if __name__ == '__main__':
    success = test_single_api_call()
    sys.exit(0 if success else 1)

