"""Quick test of directional cone logic"""

import logging
from isochrone_router import is_in_directional_cone

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test: going south (180°) with cone check
destination_bearing = 180  # South
distance_to_goal = 30

logger.info("Testing directional cone for south-bound route:")
logger.info(f"Destination bearing: {destination_bearing}°")
logger.info(f"Distance to goal: {distance_to_goal}nm")
logger.info("")

test_headings = [0, 45, 90, 135, 180, 225, 270, 315]

for heading in test_headings:
    result = is_in_directional_cone(heading, destination_bearing, distance_to_goal)
    logger.info(f"  Heading {heading:3d}deg = {'ALLOWED' if result else 'SKIPPED'}")

