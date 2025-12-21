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
  heading: number | null;  // Heading used to reach this waypoint (degrees, 0-360)
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

export type GridPointWeather = {
  time: string;
  windSpeed: number;
  windDirection: number;
  windSustained: number;
  windGusts: number;
  waveHeight: number;
  precipitation: number;
  visibility: number;
  temperature: number;
};

export type GridPointWithWeather = {
  lat: number;
  lng: number;
  hourlyWeather: GridPointWeather[];
};

export type WeatherGrid = {
  gridPoints: Coordinates[];
  bounds?: {
    min_lat?: number;
    max_lat?: number;
    min_lng?: number;
    max_lng?: number;
  };
  times?: string[];  // ISO timestamp strings for each hour
  gridPointsWithWeather?: GridPointWithWeather[];  // Grid points with hourly weather data
};

export type RouteResponse = {
  routes: Route[];
  calculatedAt: string;
  weatherGrid?: WeatherGrid;
};

export type BoatType = 'sailboat' | 'motorboat' | 'catamaran';

