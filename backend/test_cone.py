"""Quick test of directional cone logic"""

from isochrone_router import is_in_directional_cone

# Test: going south (180°) with cone check
destination_bearing = 180  # South
distance_to_goal = 30

print("Testing directional cone for south-bound route:")
print(f"Destination bearing: {destination_bearing}°")
print(f"Distance to goal: {distance_to_goal}nm")
print()

test_headings = [0, 45, 90, 135, 180, 225, 270, 315]

for heading in test_headings:
    result = is_in_directional_cone(heading, destination_bearing, distance_to_goal)
    print(f"  Heading {heading:3d}deg = {'ALLOWED' if result else 'SKIPPED'}")

