"""
Land Detection - Check if coordinates are on land or water

Uses the global-land-mask package which utilizes the GLOBE dataset
(1 km resolution global land mask) to determine if a point is on land.

This allows offline land/water detection without requiring external API calls.
"""

import logging
import math
from typing import Optional

try:
    from global_land_mask import globe
    LAND_DETECTION_AVAILABLE = True
except ImportError:
    LAND_DETECTION_AVAILABLE = False
    globe = None

from models import Coordinates
from route_generator import calculate_destination

# Set up logging
logger = logging.getLogger(__name__)


# Singleton instance to cache initialization
_land_detector_initialized = False


def is_land(position: Coordinates) -> bool:
    """
    Check if a geographic position is on land.
    
    Args:
        position: Coordinates (lat, lng)
        
    Returns:
        True if position is on land, False if on water.
        Returns False if land detection is not available (graceful fallback).
    """
    global _land_detector_initialized
    
    if not LAND_DETECTION_AVAILABLE:
        if not _land_detector_initialized:
            logger.warning("global-land-mask package not available. Install with: pip install global-land-mask")
            logger.warning("Land detection disabled - all points will be treated as water.")
            _land_detector_initialized = True
        return False  # Graceful fallback: assume water if detection unavailable
    
    try:
        # global-land-mask uses (lat, lon) order
        # Returns True if on land, False if on water
        return globe.is_land(position.lat, position.lng)
    except Exception as e:
        logger.error(f"Error checking if point is on land: {e}")
        return False  # Graceful fallback: assume water on error


def is_water(position: Coordinates) -> bool:
    """
    Check if a geographic position is on water.
    
    Convenience function - inverse of is_land().
    
    Args:
        position: Coordinates (lat, lng)
        
    Returns:
        True if position is on water, False if on land.
    """
    return not is_land(position)


# Default buffer distance: 3 km = ~1.62 nautical miles
DEFAULT_LAND_BUFFER_NM = 3.0 / 1.852  # 3 km in nautical miles (~1.62 nm)


def is_close_to_land(
    position: Coordinates,
    buffer_distance_nm: float = DEFAULT_LAND_BUFFER_NM,
    sample_points: int = 16
) -> bool:
    """
    Check if a position is close to land (within buffer distance).
    
    Samples points around the position in a circle at the buffer distance.
    If any sampled point is on land, the position is considered too close to land.
    
    This is useful for pruning points that are too close to coastlines,
    which might be problematic for sailing routes.
    
    Args:
        position: Coordinates to check
        buffer_distance_nm: Buffer distance in nautical miles (default: ~1.62 nm = 3 km)
        sample_points: Number of points to sample around the circle (default: 16)
                     More points = more accurate but slower. 8-16 is usually sufficient.
        
    Returns:
        True if position is within buffer_distance_nm of land, False otherwise.
        Returns False if land detection is not available (graceful fallback).
    """
    if not LAND_DETECTION_AVAILABLE:
        return False  # Graceful fallback: assume not close to land if detection unavailable
    
    # Sample points around the position in a circle
    # We check points at the buffer distance radius
    angle_step = 360.0 / sample_points
    
    for i in range(sample_points):
        # Calculate bearing for this sample point
        bearing = i * angle_step
        
        # Calculate position at buffer distance in this direction
        sample_position = calculate_destination(position, buffer_distance_nm, bearing)
        
        # If any sample point is on land, the center is too close to land
        if is_land(sample_position):
            return True
    
    # Also check the center point itself (shouldn't be on land, but good to verify)
    if is_land(position):
        return True
    
    # None of the sampled points or center are on land
    return False

