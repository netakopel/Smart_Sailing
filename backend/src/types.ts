// Core types for the Smart Sailing Route Planner

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface RouteRequest {
  start: Coordinates;
  end: Coordinates;
  boatType: 'sailboat' | 'motorboat' | 'catamaran';
  departureTime: string; // ISO 8601 format
}

export interface Waypoint {
  position: Coordinates;
  estimatedArrival: string;
  weather?: WaypointWeather;
}

export interface WaypointWeather {
  windSpeed: number;      // knots
  windDirection: number;  // degrees (0-360)
  waveHeight: number;     // meters
  precipitation: number;  // mm
  visibility: number;     // km
  temperature: number;    // celsius
}

export interface Route {
  name: string;
  type: 'direct' | 'northern' | 'southern';
  score: number;          // 0-100
  distance: number;       // nautical miles
  estimatedTime: string;  // human readable
  estimatedHours: number;
  waypoints: Waypoint[];
  warnings: string[];
  pros: string[];
  cons: string[];
}

export interface RouteResponse {
  routes: Route[];
  calculatedAt: string;
}

// Boat characteristics for calculations
export interface BoatProfile {
  type: string;
  avgSpeed: number;       // knots in ideal conditions
  maxSpeed: number;       // knots
  optimalWindAngle: number; // degrees from bow
  minWindSpeed: number;   // knots (for sailboats)
  maxSafeWindSpeed: number; // knots
  maxSafeWaveHeight: number; // meters
}

export const BOAT_PROFILES: Record<string, BoatProfile> = {
  sailboat: {
    type: 'sailboat',
    avgSpeed: 6,
    maxSpeed: 12,
    optimalWindAngle: 120,  // broad reach
    minWindSpeed: 5,
    maxSafeWindSpeed: 30,
    maxSafeWaveHeight: 3,
  },
  motorboat: {
    type: 'motorboat',
    avgSpeed: 15,
    maxSpeed: 30,
    optimalWindAngle: 0,    // doesn't matter for motor
    minWindSpeed: 0,
    maxSafeWindSpeed: 35,
    maxSafeWaveHeight: 2.5,
  },
  catamaran: {
    type: 'catamaran',
    avgSpeed: 8,
    maxSpeed: 15,
    optimalWindAngle: 110,
    minWindSpeed: 6,
    maxSafeWindSpeed: 28,
    maxSafeWaveHeight: 2,
  },
};

