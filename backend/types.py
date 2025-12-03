"""
Type definitions for Smart Sailing Route Planner
Using Python dataclasses for clean, typed data structures
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class BoatType(Enum):
    """Types of boats we support"""
    SAILBOAT = "sailboat"
    MOTORBOAT = "motorboat"
    CATAMARAN = "catamaran"


class RouteType(Enum):
    """Types of routes we generate"""
    DIRECT = "direct"
    NORTHERN = "northern"
    SOUTHERN = "southern"


@dataclass
class Coordinates:
    """A point on Earth (latitude/longitude)"""
    lat: float  # Latitude (-90 to 90)
    lng: float  # Longitude (-180 to 180)


@dataclass
class WaypointWeather:
    """Weather conditions at a specific point and time"""
    wind_speed: float       # knots
    wind_direction: float   # degrees (0-360, where wind comes FROM)
    wave_height: float      # meters
    precipitation: float    # mm
    visibility: float       # km
    temperature: float      # celsius


@dataclass
class Waypoint:
    """A point along the route with arrival time and weather"""
    position: Coordinates
    estimated_arrival: str  # ISO 8601 format
    weather: Optional[WaypointWeather] = None


@dataclass
class Route:
    """A complete route with scoring and details"""
    name: str
    route_type: RouteType
    score: int              # 0-100
    distance: float         # nautical miles
    estimated_time: str     # human readable (e.g., "12h 30m")
    estimated_hours: float
    waypoints: List[Waypoint]
    warnings: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)


@dataclass
class RouteRequest:
    """Input from user: where they want to go"""
    start: Coordinates
    end: Coordinates
    boat_type: BoatType
    departure_time: str  # ISO 8601 format


@dataclass
class RouteResponse:
    """Output to user: route recommendations"""
    routes: List[Route]
    calculated_at: str


@dataclass
class BoatProfile:
    """Characteristics of a boat type that affect routing"""
    boat_type: BoatType
    avg_speed: float          # knots in ideal conditions
    max_speed: float          # knots
    optimal_wind_angle: float # degrees from bow (best sailing angle)
    min_wind_speed: float     # knots (for sailboats)
    max_safe_wind_speed: float   # knots
    max_safe_wave_height: float  # meters


# Boat profiles - characteristics for each boat type
BOAT_PROFILES = {
    BoatType.SAILBOAT: BoatProfile(
        boat_type=BoatType.SAILBOAT,
        avg_speed=6,
        max_speed=12,
        optimal_wind_angle=120,  # broad reach is fastest
        min_wind_speed=5,
        max_safe_wind_speed=30,
        max_safe_wave_height=3,
    ),
    BoatType.MOTORBOAT: BoatProfile(
        boat_type=BoatType.MOTORBOAT,
        avg_speed=15,
        max_speed=30,
        optimal_wind_angle=0,    # doesn't matter for motor
        min_wind_speed=0,
        max_safe_wind_speed=35,
        max_safe_wave_height=2.5,
    ),
    BoatType.CATAMARAN: BoatProfile(
        boat_type=BoatType.CATAMARAN,
        avg_speed=8,
        max_speed=15,
        optimal_wind_angle=110,
        min_wind_speed=6,
        max_safe_wind_speed=28,
        max_safe_wave_height=2,
    ),
}

