// Route Generator - Creates 3 route options between start and end points

import { Coordinates, Waypoint, RouteRequest, BOAT_PROFILES } from './types';

/**
 * Calculate distance between two points using Haversine formula
 * Returns distance in nautical miles
 */
export function calculateDistance(start: Coordinates, end: Coordinates): number {
  const R = 3440.065; // Earth's radius in nautical miles
  const lat1 = toRadians(start.lat);
  const lat2 = toRadians(end.lat);
  const deltaLat = toRadians(end.lat - start.lat);
  const deltaLng = toRadians(end.lng - start.lng);

  const a = Math.sin(deltaLat / 2) * Math.sin(deltaLat / 2) +
            Math.cos(lat1) * Math.cos(lat2) *
            Math.sin(deltaLng / 2) * Math.sin(deltaLng / 2);
  
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  
  return R * c;
}

/**
 * Calculate bearing from start to end point
 * Returns bearing in degrees (0-360)
 */
export function calculateBearing(start: Coordinates, end: Coordinates): number {
  const lat1 = toRadians(start.lat);
  const lat2 = toRadians(end.lat);
  const deltaLng = toRadians(end.lng - start.lng);

  const y = Math.sin(deltaLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) -
            Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng);
  
  const bearing = toDegrees(Math.atan2(y, x));
  return (bearing + 360) % 360;
}

/**
 * Calculate a point at given distance and bearing from start
 */
export function calculateDestination(
  start: Coordinates, 
  distance: number, 
  bearing: number
): Coordinates {
  const R = 3440.065; // Earth's radius in nautical miles
  const lat1 = toRadians(start.lat);
  const lng1 = toRadians(start.lng);
  const bearingRad = toRadians(bearing);

  const lat2 = Math.asin(
    Math.sin(lat1) * Math.cos(distance / R) +
    Math.cos(lat1) * Math.sin(distance / R) * Math.cos(bearingRad)
  );

  const lng2 = lng1 + Math.atan2(
    Math.sin(bearingRad) * Math.sin(distance / R) * Math.cos(lat1),
    Math.cos(distance / R) - Math.sin(lat1) * Math.sin(lat2)
  );

  return {
    lat: toDegrees(lat2),
    lng: toDegrees(lng2),
  };
}

function toRadians(degrees: number): number {
  return degrees * (Math.PI / 180);
}

function toDegrees(radians: number): number {
  return radians * (180 / Math.PI);
}

/**
 * Generate waypoints along a direct path
 */
function generateDirectWaypoints(
  start: Coordinates,
  end: Coordinates,
  numWaypoints: number,
  departureTime: Date,
  avgSpeed: number
): Waypoint[] {
  const waypoints: Waypoint[] = [];
  const totalDistance = calculateDistance(start, end);
  const bearing = calculateBearing(start, end);
  
  for (let i = 0; i <= numWaypoints; i++) {
    const fraction = i / numWaypoints;
    const distanceFromStart = totalDistance * fraction;
    
    let position: Coordinates;
    if (i === 0) {
      position = start;
    } else if (i === numWaypoints) {
      position = end;
    } else {
      position = calculateDestination(start, distanceFromStart, bearing);
    }
    
    // Estimate arrival time based on average speed
    const hoursFromStart = distanceFromStart / avgSpeed;
    const arrivalTime = new Date(departureTime.getTime() + hoursFromStart * 3600000);
    
    waypoints.push({
      position,
      estimatedArrival: arrivalTime.toISOString(),
    });
  }
  
  return waypoints;
}

/**
 * Generate waypoints along a curved path (offset to north or south)
 */
function generateCurvedWaypoints(
  start: Coordinates,
  end: Coordinates,
  numWaypoints: number,
  departureTime: Date,
  avgSpeed: number,
  offsetDirection: 'north' | 'south',
  offsetAmount: number // in nautical miles
): Waypoint[] {
  const waypoints: Waypoint[] = [];
  const totalDistance = calculateDistance(start, end);
  const mainBearing = calculateBearing(start, end);
  
  // Perpendicular bearing for offset
  const perpBearing = offsetDirection === 'north' 
    ? (mainBearing - 90 + 360) % 360 
    : (mainBearing + 90) % 360;
  
  let cumulativeDistance = 0;
  
  for (let i = 0; i <= numWaypoints; i++) {
    const fraction = i / numWaypoints;
    
    // Create a sine curve for smooth offset (max at middle)
    const offsetFactor = Math.sin(fraction * Math.PI);
    const currentOffset = offsetAmount * offsetFactor;
    
    // First, get point on direct line
    const distanceFromStart = totalDistance * fraction;
    let position: Coordinates;
    
    if (i === 0) {
      position = start;
    } else if (i === numWaypoints) {
      position = end;
    } else {
      const directPoint = calculateDestination(start, distanceFromStart, mainBearing);
      // Then offset it perpendicular to the route
      position = calculateDestination(directPoint, currentOffset, perpBearing);
    }
    
    // Calculate actual distance traveled (segment by segment)
    if (i > 0) {
      cumulativeDistance += calculateDistance(waypoints[i - 1].position, position);
    }
    
    const hoursFromStart = cumulativeDistance / avgSpeed;
    const arrivalTime = new Date(departureTime.getTime() + hoursFromStart * 3600000);
    
    waypoints.push({
      position,
      estimatedArrival: arrivalTime.toISOString(),
    });
  }
  
  return waypoints;
}

/**
 * Calculate total route distance from waypoints
 */
export function calculateRouteDistance(waypoints: Waypoint[]): number {
  let total = 0;
  for (let i = 1; i < waypoints.length; i++) {
    total += calculateDistance(waypoints[i - 1].position, waypoints[i].position);
  }
  return total;
}

/**
 * Format hours into human-readable string
 */
export function formatDuration(hours: number): string {
  if (hours < 1) {
    return `${Math.round(hours * 60)} minutes`;
  }
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  if (m === 0) {
    return `${h} hour${h !== 1 ? 's' : ''}`;
  }
  return `${h}h ${m}m`;
}

export interface GeneratedRoute {
  name: string;
  type: 'direct' | 'northern' | 'southern';
  waypoints: Waypoint[];
  distance: number;
  estimatedHours: number;
  estimatedTime: string;
}

/**
 * Main function: Generate 3 route options
 */
export function generateRoutes(request: RouteRequest): GeneratedRoute[] {
  const { start, end, boatType, departureTime } = request;
  const boat = BOAT_PROFILES[boatType];
  const departureDate = new Date(departureTime);
  const numWaypoints = 5; // 6 points total including start/end
  
  const directDistance = calculateDistance(start, end);
  
  // Offset amount scales with distance (roughly 5% of distance, min 10nm, max 50nm)
  const offsetAmount = Math.min(50, Math.max(10, directDistance * 0.05));
  
  // Generate 3 routes
  const routes: GeneratedRoute[] = [];
  
  // 1. Direct Route
  const directWaypoints = generateDirectWaypoints(
    start, end, numWaypoints, departureDate, boat.avgSpeed
  );
  const directRouteDistance = calculateRouteDistance(directWaypoints);
  const directHours = directRouteDistance / boat.avgSpeed;
  
  routes.push({
    name: 'Direct Route',
    type: 'direct',
    waypoints: directWaypoints,
    distance: Math.round(directRouteDistance * 10) / 10,
    estimatedHours: directHours,
    estimatedTime: formatDuration(directHours),
  });
  
  // 2. Northern Route
  const northernWaypoints = generateCurvedWaypoints(
    start, end, numWaypoints, departureDate, boat.avgSpeed, 'north', offsetAmount
  );
  const northernDistance = calculateRouteDistance(northernWaypoints);
  const northernHours = northernDistance / boat.avgSpeed;
  
  routes.push({
    name: 'Northern Route',
    type: 'northern',
    waypoints: northernWaypoints,
    distance: Math.round(northernDistance * 10) / 10,
    estimatedHours: northernHours,
    estimatedTime: formatDuration(northernHours),
  });
  
  // 3. Southern Route
  const southernWaypoints = generateCurvedWaypoints(
    start, end, numWaypoints, departureDate, boat.avgSpeed, 'south', offsetAmount
  );
  const southernDistance = calculateRouteDistance(southernWaypoints);
  const southernHours = southernDistance / boat.avgSpeed;
  
  routes.push({
    name: 'Southern Route',
    type: 'southern',
    waypoints: southernWaypoints,
    distance: Math.round(southernDistance * 10) / 10,
    estimatedHours: southernHours,
    estimatedTime: formatDuration(southernHours),
  });
  
  return routes;
}

