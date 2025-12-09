"""
Polar Diagrams Module

This module defines boat performance characteristics using polar diagrams.
A polar diagram maps (wind_speed, wind_angle) → boat_speed for different boat types.

Key Concepts:
- TWS (True Wind Speed): Wind speed in knots
- TWA (True Wind Angle): Angle between boat heading and wind direction (0-180°)
- Boat Speed: Speed in knots achieved at given TWS and TWA
- VMG (Velocity Made Good): Component of speed toward destination
- No-Go Zone: Angles < 45° where sailing is impossible/impractical
"""

import math
from typing import Dict, Tuple, Optional
from enum import Enum


class BoatType(str, Enum):
    """Supported boat types"""
    SAILBOAT = "sailboat"
    MOTORBOAT = "motorboat"
    CATAMARAN = "catamaran"


# ============================================================================
# POLAR DATA TABLES
# ============================================================================

# Polar structure: {wind_speed_knots: {wind_angle_degrees: boat_speed_knots}}
# Wind angles are 0-180° (symmetric - same performance on port/starboard)
# Data is based on typical performance for each boat class

SAILBOAT_POLAR = {
    # Light air (6 knots wind)
    6: {
        0: 0.0,      # Dead upwind - impossible
        30: 0.0,     # Too close to wind (no-go zone)
        45: 0.0,     # Edge of no-go zone
        52: 3.2,     # Close-hauled (optimal upwind angle)
        60: 3.8,     # Close-hauled
        75: 4.1,     # Close reach
        90: 4.3,     # Beam reach
        110: 4.7,    # Broad reach (fastest angle for this wind)
        135: 4.5,    # Broad reach
        150: 4.0,    # Running
        180: 3.5,    # Dead downwind (slower than angled)
    },
    # Moderate wind (10 knots)
    10: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 5.5,     # Good upwind speed
        60: 6.2,
        75: 6.8,
        90: 7.2,     # Excellent beam reach
        110: 7.8,    # Peak speed (broad reach)
        135: 7.5,
        150: 6.8,
        180: 6.0,
    },
    # Fresh breeze (15 knots)
    15: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 7.5,
        60: 8.2,
        75: 9.0,
        90: 9.5,
        110: 10.2,   # Maximum hull speed approached
        135: 9.8,
        150: 9.0,
        180: 8.0,
    },
    # Strong wind (20 knots)
    20: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 8.5,     # Starting to reef sails
        60: 9.2,
        75: 10.0,
        90: 10.5,
        110: 11.0,   # Hull speed limit
        135: 10.5,
        150: 9.5,
        180: 8.5,
    },
    # Very strong wind (25 knots)
    25: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 8.8,     # Reefed sails, not much faster
        60: 9.5,
        75: 10.2,
        90: 10.8,
        110: 11.2,   # Hull speed limit
        135: 10.8,
        150: 10.0,
        180: 9.0,
    },
    # Dangerous wind (30 knots)
    30: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 9.0,     # Heavily reefed
        60: 9.8,
        75: 10.5,
        90: 11.0,
        110: 11.5,
        135: 11.0,
        150: 10.2,
        180: 9.2,
    },
    # Storm conditions (35 knots)
    35: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 9.0,     # Survival sailing
        60: 9.5,
        75: 10.0,
        90: 10.5,
        110: 11.0,
        135: 10.5,
        150: 10.0,
        180: 9.0,
    },
}

CATAMARAN_POLAR = {
    # Catamarans are faster than monohulls, especially off-wind
    6: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 4.0,     # Better upwind than monohull
        60: 4.8,
        75: 5.5,
        90: 6.0,
        110: 6.5,
        135: 6.2,
        150: 5.5,
        180: 5.0,
    },
    10: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 7.0,
        60: 8.0,
        75: 9.0,
        90: 10.0,
        110: 11.0,   # Much faster than monohull
        135: 10.5,
        150: 9.5,
        180: 8.5,
    },
    15: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 10.0,
        60: 11.5,
        75: 13.0,
        90: 14.5,
        110: 16.0,   # Can exceed wind speed!
        135: 15.5,
        150: 14.0,
        180: 12.5,
    },
    20: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 12.0,
        60: 14.0,
        75: 16.0,
        90: 18.0,
        110: 20.0,   # Performance catamaran speeds
        135: 19.0,
        150: 17.0,
        180: 15.0,
    },
    25: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 13.5,
        60: 15.5,
        75: 17.5,
        90: 19.5,
        110: 21.5,
        135: 20.5,
        150: 18.5,
        180: 16.5,
    },
    30: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 14.0,    # Starting to reef
        60: 16.0,
        75: 18.0,
        90: 20.0,
        110: 22.0,
        135: 21.0,
        150: 19.0,
        180: 17.0,
    },
    35: {
        0: 0.0,
        30: 0.0,
        45: 0.0,
        52: 14.0,
        60: 16.0,
        75: 18.0,
        90: 20.0,
        110: 21.5,
        135: 20.5,
        150: 19.0,
        180: 17.0,
    },
}

MOTORBOAT_POLAR = {
    # Motorboats maintain constant speed regardless of wind angle
    # Wind affects speed slightly (headwind slows, tailwind helps)
    6: {
        0: 18.0,     # Motorboats can go any direction
        30: 18.0,
        45: 18.0,
        52: 18.0,
        60: 18.0,
        75: 18.0,
        90: 18.0,
        110: 18.0,
        135: 18.0,
        150: 18.0,
        180: 18.0,
    },
    10: {
        0: 17.5,     # Slight headwind penalty
        30: 17.5,
        45: 18.0,
        52: 18.0,
        60: 18.0,
        75: 18.5,
        90: 18.5,
        110: 19.0,
        135: 19.0,
        150: 19.0,
        180: 19.5,   # Tailwind boost
    },
    15: {
        0: 17.0,
        30: 17.0,
        45: 17.5,
        52: 17.5,
        60: 18.0,
        75: 18.5,
        90: 18.5,
        110: 19.0,
        135: 19.0,
        150: 19.5,
        180: 20.0,
    },
    20: {
        0: 16.0,     # Significant headwind impact
        30: 16.0,
        45: 16.5,
        52: 17.0,
        60: 17.5,
        75: 18.0,
        90: 18.5,
        110: 19.0,
        135: 19.5,
        150: 20.0,
        180: 20.5,
    },
    25: {
        0: 15.0,     # Strong headwind
        30: 15.0,
        45: 15.5,
        52: 16.0,
        60: 17.0,
        75: 17.5,
        90: 18.0,
        110: 19.0,
        135: 19.5,
        150: 20.0,
        180: 21.0,
    },
    30: {
        0: 14.0,     # Dangerous to operate
        30: 14.0,
        45: 14.5,
        52: 15.0,
        60: 16.0,
        75: 17.0,
        90: 17.5,
        110: 18.5,
        135: 19.0,
        150: 19.5,
        180: 20.5,
    },
    35: {
        0: 12.0,     # Storm conditions
        30: 12.0,
        45: 13.0,
        52: 14.0,
        60: 15.0,
        75: 16.0,
        90: 17.0,
        110: 18.0,
        135: 18.5,
        150: 19.0,
        180: 20.0,
    },
}

# Lookup table for all boat types
POLARS: Dict[BoatType, Dict[int, Dict[int, float]]] = {
    BoatType.SAILBOAT: SAILBOAT_POLAR,
    BoatType.CATAMARAN: CATAMARAN_POLAR,
    BoatType.MOTORBOAT: MOTORBOAT_POLAR,
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_angle(angle: float) -> float:
    """
    Normalize angle to 0-360 range.
    
    Args:
        angle: Angle in degrees (can be negative or > 360)
    
    Returns:
        Angle normalized to 0-360 range
    """
    while angle < 0:
        angle += 360
    while angle >= 360:
        angle -= 360
    return angle


def calculate_wind_angle(boat_heading: float, wind_direction: float) -> float:
    """
    Calculate the true wind angle (TWA) relative to boat heading.
    
    TWA is always 0-180° (symmetric on port/starboard).
    
    Args:
        boat_heading: Direction boat is pointing (0-360°, 0=North)
        wind_direction: Direction wind is coming FROM (0-360°, 0=North)
    
    Returns:
        Wind angle relative to boat (0-180°)
    
    Example:
        - Boat heading 090° (East), Wind from 090° (East) → TWA = 0° (dead upwind)
        - Boat heading 090° (East), Wind from 270° (West) → TWA = 180° (dead downwind)
        - Boat heading 000° (North), Wind from 045° (NE) → TWA = 45° (close-hauled)
    """
    # Calculate relative angle
    relative = abs(boat_heading - wind_direction)
    relative = normalize_angle(relative)
    
    # Mirror to 0-180° range (polars are symmetric)
    if relative > 180:
        relative = 360 - relative
    
    return relative


def bilinear_interpolate(
    x: float, y: float,
    x1: float, x2: float,
    y1: float, y2: float,
    q11: float, q12: float, q21: float, q22: float
) -> float:
    """
    Perform bilinear interpolation for a point (x, y) within a grid cell.
    
    Grid corners:
        (x1, y2) q12 ---- q22 (x2, y2)
           |               |
           |      (x,y)    |
           |               |
        (x1, y1) q11 ---- q21 (x2, y1)
    
    Args:
        x, y: Target point coordinates
        x1, x2: X bounds (x1 <= x <= x2)
        y1, y2: Y bounds (y1 <= y <= y2)
        q11, q12, q21, q22: Values at four corners
    
    Returns:
        Interpolated value at (x, y)
    """
    # Handle edge case where bounds are equal
    if x2 == x1:
        if y2 == y1:
            return q11  # Point exactly on corner
        # Linear interpolation in y only
        return q11 + (q12 - q11) * (y - y1) / (y2 - y1)
    
    if y2 == y1:
        # Linear interpolation in x only
        return q11 + (q21 - q11) * (x - x1) / (x2 - x1)
    
    # Full bilinear interpolation
    # Interpolate in x direction
    r1 = q11 * (x2 - x) / (x2 - x1) + q21 * (x - x1) / (x2 - x1)
    r2 = q12 * (x2 - x) / (x2 - x1) + q22 * (x - x1) / (x2 - x1)
    
    # Interpolate in y direction
    result = r1 * (y2 - y) / (y2 - y1) + r2 * (y - y1) / (y2 - y1)
    
    return result


# ============================================================================
# MAIN POLAR FUNCTIONS
# ============================================================================

def get_boat_speed(
    wind_speed: float,
    wind_angle: float,
    boat_type: str
) -> float:
    """
    Get boat speed for given wind conditions using polar diagram.
    
    Uses bilinear interpolation between tabulated polar data points.
    
    Args:
        wind_speed: True wind speed in knots
        wind_angle: True wind angle (0-180°, relative to boat heading)
        boat_type: Type of boat ('sailboat', 'motorboat', 'catamaran')
    
    Returns:
        Boat speed in knots (0 if in no-go zone or invalid conditions)
    
    Examples:
        >>> get_boat_speed(10, 90, 'sailboat')
        7.2  # Beam reach in 10 knots
        
        >>> get_boat_speed(10, 30, 'sailboat')
        0.0  # No-go zone
        
        >>> get_boat_speed(12, 95, 'sailboat')
        7.4  # Interpolated between 10 and 15 knots, 90 and 110 degrees
    """
    # Validate inputs
    if wind_speed < 0:
        return 0.0
    
    # Normalize wind angle to 0-180
    wind_angle = abs(wind_angle)
    if wind_angle > 180:
        wind_angle = 360 - wind_angle
    
    # Get polar table for boat type
    try:
        boat_type_enum = BoatType(boat_type.lower())
        polar = POLARS[boat_type_enum]
    except (ValueError, KeyError):
        # Unknown boat type, default to sailboat
        polar = POLARS[BoatType.SAILBOAT]
    
    # Get available wind speeds and angles from polar table
    wind_speeds = sorted(polar.keys())
    wind_angles = sorted(polar[wind_speeds[0]].keys())  # All wind speeds have same angles
    
    # Handle out-of-range wind speeds
    if wind_speed <= wind_speeds[0]:
        # Below minimum wind speed - use lowest available
        ws_low = ws_high = wind_speeds[0]
    elif wind_speed >= wind_speeds[-1]:
        # Above maximum wind speed - use highest available
        ws_low = ws_high = wind_speeds[-1]
    else:
        # Find bounding wind speeds
        ws_low = wind_speeds[0]
        ws_high = wind_speeds[-1]
        for i in range(len(wind_speeds) - 1):
            if wind_speeds[i] <= wind_speed <= wind_speeds[i + 1]:
                ws_low = wind_speeds[i]
                ws_high = wind_speeds[i + 1]
                break
    
    # Handle out-of-range wind angles
    if wind_angle <= wind_angles[0]:
        wa_low = wa_high = wind_angles[0]
    elif wind_angle >= wind_angles[-1]:
        wa_low = wa_high = wind_angles[-1]
    else:
        # Find bounding wind angles
        wa_low = wind_angles[0]
        wa_high = wind_angles[-1]
        for i in range(len(wind_angles) - 1):
            if wind_angles[i] <= wind_angle <= wind_angles[i + 1]:
                wa_low = wind_angles[i]
                wa_high = wind_angles[i + 1]
                break
    
    # Get boat speeds at four corners of interpolation grid
    q11 = polar[ws_low][wa_low]    # Lower-left
    q12 = polar[ws_low][wa_high]   # Upper-left
    q21 = polar[ws_high][wa_low]   # Lower-right
    q22 = polar[ws_high][wa_high]  # Upper-right
    
    # Perform bilinear interpolation (handles all cases: exact match, linear, bilinear)
    return bilinear_interpolate(
        wind_speed, wind_angle,
        ws_low, ws_high,
        wa_low, wa_high,
        q11, q12, q21, q22
    )


def get_optimal_vmg_angle(
    wind_speed: float,
    boat_type: str,
    destination_bearing: float,
    wind_direction: float
) -> Tuple[float, float]:
    """
    Calculate optimal heading to maximize VMG (Velocity Made Good) toward destination.
    
    VMG = boat_speed × cos(angle_off_course)
    
    This function tries multiple headings and finds the one that maximizes
    progress toward the destination.
    
    Args:
        wind_speed: True wind speed in knots
        boat_type: Type of boat ('sailboat', 'motorboat', 'catamaran')
        destination_bearing: Bearing to destination (0-360°, 0=North)
        wind_direction: Direction wind is coming FROM (0-360°, 0=North)
    
    Returns:
        Tuple of (optimal_heading, max_vmg)
        - optimal_heading: Best heading in degrees (0-360°)
        - max_vmg: Maximum VMG in knots
    
    Example:
        Destination is North (000°), wind from North (000°)
        → Can't sail directly, must tack at ~52° or 308°
        → Returns (052°, 3.7 knots) or (308°, 3.7 knots) depending on which is better
    """
    # Try headings every 5 degrees
    best_heading = destination_bearing
    max_vmg = 0.0
    
    for heading in range(0, 360, 5):
        # Calculate wind angle for this heading
        twa = calculate_wind_angle(heading, wind_direction)
        
        # Get boat speed at this heading
        boat_speed = get_boat_speed(wind_speed, twa, boat_type)
        
        if boat_speed == 0:
            continue  # In no-go zone
        
        # Calculate VMG toward destination
        vmg = calculate_vmg(boat_speed, heading, destination_bearing)
        
        # Track best heading
        if vmg > max_vmg:
            max_vmg = vmg
            best_heading = heading
    
    return best_heading, max_vmg


def calculate_vmg(
    boat_speed: float,
    boat_heading: float,
    destination_bearing: float
) -> float:
    """
    Calculate Velocity Made Good (VMG) toward destination.
    
    VMG = boat_speed × cos(angle_off_course)
    
    Args:
        boat_speed: Boat speed in knots
        boat_heading: Direction boat is traveling (0-360°)
        destination_bearing: Bearing to destination (0-360°)
    
    Returns:
        VMG in knots (component of speed toward destination)
    """
    angle_off = abs(boat_heading - destination_bearing)
    if angle_off > 180:
        angle_off = 360 - angle_off
    
    return boat_speed * math.cos(math.radians(angle_off))


def is_in_no_go_zone(wind_angle: float, boat_type: str) -> bool:
    """
    Check if wind angle is in the no-go zone for given boat type.
    
    Args:
        wind_angle: True wind angle (0-180°)
        boat_type: Type of boat
    
    Returns:
        True if in no-go zone (cannot sail this angle)
    """
    # Motorboats have no restrictions
    if boat_type.lower() == BoatType.MOTORBOAT.value:
        return False
    
    # Sailboats and catamarans cannot sail < 45° to wind
    return abs(wind_angle) < 45


# ============================================================================
# TESTING / DEBUG
# ============================================================================

if __name__ == "__main__":
    # Test basic polar lookups
    print("=== Polar Diagram Tests ===\n")
    
    print("Test 1: Exact lookup - Sailboat, 10 knots, 90° (beam reach)")
    speed = get_boat_speed(10, 90, "sailboat")
    print(f"  Result: {speed:.1f} knots (expected: 7.2)\n")
    
    print("Test 2: No-go zone - Sailboat, 10 knots, 30°")
    speed = get_boat_speed(10, 30, "sailboat")
    print(f"  Result: {speed:.1f} knots (expected: 0.0)\n")
    
    print("Test 3: Interpolation - Sailboat, 12 knots, 95°")
    speed = get_boat_speed(12, 95, "sailboat")
    print(f"  Result: {speed:.1f} knots (expected: ~7.5-8.0)\n")
    
    print("Test 4: Catamaran speed - 15 knots, 110° (broad reach)")
    speed = get_boat_speed(15, 110, "catamaran")
    print(f"  Result: {speed:.1f} knots (expected: 16.0)\n")
    
    print("Test 5: Motorboat - 15 knots wind, any angle")
    speed_upwind = get_boat_speed(15, 0, "motorboat")
    speed_downwind = get_boat_speed(15, 180, "motorboat")
    print(f"  Upwind: {speed_upwind:.1f} knots")
    print(f"  Downwind: {speed_downwind:.1f} knots")
    print(f"  (Motorboat less affected by wind angle)\n")
    
    print("Test 6: VMG optimization - Destination North, Wind from North")
    optimal_heading, max_vmg = get_optimal_vmg_angle(
        wind_speed=15,
        boat_type="sailboat",
        destination_bearing=0,   # North
        wind_direction=0         # Wind from North
    )
    print(f"  Cannot sail directly upwind (in no-go zone)")
    print(f"  Optimal heading: {optimal_heading}°")
    print(f"  VMG: {max_vmg:.2f} knots")
    print(f"  (Should be around 50-52° or 308-310° with VMG ~5-6 knots)\n")
    
    print("Test 7: VMG optimization - Destination North, Wind from East")
    optimal_heading, max_vmg = get_optimal_vmg_angle(
        wind_speed=15,
        boat_type="sailboat",
        destination_bearing=0,   # North
        wind_direction=90        # Wind from East
    )
    print(f"  Beam reach - good conditions")
    print(f"  Optimal heading: {optimal_heading}°")
    print(f"  VMG: {max_vmg:.2f} knots")
    print(f"  (Should be close to 0° with excellent VMG ~9-10 knots)\n")
    
    print("=== All tests complete ===")

