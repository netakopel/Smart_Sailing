// Type definitions matching backend API response (camelCase)

export type Coordinates = {
  lat: number;
  lng: number;
};

export type WeatherData = {
  windSpeed: number;       // knots
  windSustained: number;   // knots
  windGusts: number;       // knots
  windDirection: number;   // degrees
  waveHeight: number;      // meters
  temperature: number;     // celsius
  precipitation: number;   // mm
  visibility: number;      // km
};

export type Waypoint = {
  position: Coordinates;
  weather: WeatherData | null;
  estimatedArrival: string;
};

export type NoGoZoneViolation = {
  segmentIndex: number;  // Which waypoint segment (0->1, 1->2, etc)
  heading: number;       // Heading of the segment in degrees
  windAngle: number;     // Wind angle in degrees
};

export type Route = {
  name: string;
  type: 'direct' | 'port' | 'starboard';
  score: number;
  distance: number;         // km
  estimatedTime: string;    // e.g., "13h 25m"
  estimatedHours: number;
  waypoints: Waypoint[];
  warnings: string[];
  pros: string[];
  cons: string[];
  noGoZoneViolations?: NoGoZoneViolation[];
};

export type RouteRequest = {
  start: Coordinates;
  end: Coordinates;
  boat_type: 'sailboat' | 'motorboat' | 'catamaran';
  departure_time?: string;
};

export type RouteResponse = {
  routes: Route[];
  calculatedAt: string;
};

export type BoatType = 'sailboat' | 'motorboat' | 'catamaran';

