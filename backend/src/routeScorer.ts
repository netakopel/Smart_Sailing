// Route Scorer - Calculates safety and efficiency scores for routes

import { Waypoint, Route, BoatProfile, BOAT_PROFILES, WaypointWeather } from './types';
import { GeneratedRoute, calculateBearing } from './routeGenerator';
import { summarizeWeather } from './weatherFetcher';

/**
 * Calculate wind angle relative to boat heading
 * Returns angle between 0-180 degrees
 * 0 = headwind (bad for sailing)
 * 90 = beam reach (sidewind)
 * 180 = downwind/running
 */
function calculateWindAngle(boatHeading: number, windDirection: number): number {
  // Wind direction is where wind comes FROM, so we need to reverse it
  // to get where it's going TO, then compare with boat heading
  const windTo = (windDirection + 180) % 360;
  let angle = Math.abs(boatHeading - windTo);
  if (angle > 180) {
    angle = 360 - angle;
  }
  return angle;
}

/**
 * Score wind conditions for a segment
 * Returns 0-100 score
 */
function scoreWindConditions(
  weather: WaypointWeather,
  boatHeading: number,
  boat: BoatProfile
): { score: number; notes: string[] } {
  const notes: string[] = [];
  let score = 100;
  
  const windAngle = calculateWindAngle(boatHeading, weather.windDirection);
  
  // For sailboats, wind angle matters a lot
  if (boat.type === 'sailboat' || boat.type === 'catamaran') {
    // Too little wind
    if (weather.windSpeed < boat.minWindSpeed) {
      score -= 30;
      notes.push(`Low wind (${weather.windSpeed}kt) - may need motor`);
    }
    
    // Headwind penalty (sailing into wind is slow/impossible)
    if (windAngle < 45) {
      score -= 25;
      notes.push('Headwind - will need to tack');
    } else if (windAngle >= 90 && windAngle <= 150) {
      // Beam reach to broad reach is ideal
      score += 10;
    }
  }
  
  // High wind penalty for all boats
  if (weather.windSpeed > boat.maxSafeWindSpeed) {
    score -= 40;
    notes.push(`Dangerous wind: ${weather.windSpeed}kt exceeds safe limit`);
  } else if (weather.windSpeed > boat.maxSafeWindSpeed * 0.8) {
    score -= 20;
    notes.push(`Strong wind: ${weather.windSpeed}kt - challenging conditions`);
  }
  
  return { score: Math.max(0, Math.min(100, score)), notes };
}

/**
 * Score wave conditions
 */
function scoreWaveConditions(
  waveHeight: number,
  boat: BoatProfile
): { score: number; notes: string[] } {
  const notes: string[] = [];
  let score = 100;
  
  if (waveHeight > boat.maxSafeWaveHeight) {
    score -= 40;
    notes.push(`Dangerous waves: ${waveHeight}m exceeds safe limit`);
  } else if (waveHeight > boat.maxSafeWaveHeight * 0.7) {
    score -= 20;
    notes.push(`Rough seas: ${waveHeight}m waves`);
  } else if (waveHeight < 0.5) {
    score += 5;
    notes.push('Calm seas');
  }
  
  return { score: Math.max(0, Math.min(100, score)), notes };
}

/**
 * Score visibility and precipitation
 */
function scoreVisibilityConditions(
  weather: WaypointWeather
): { score: number; notes: string[] } {
  const notes: string[] = [];
  let score = 100;
  
  if (weather.visibility < 2) {
    score -= 30;
    notes.push('Poor visibility - fog or heavy precipitation');
  } else if (weather.visibility < 5) {
    score -= 15;
    notes.push('Reduced visibility');
  }
  
  if (weather.precipitation > 5) {
    score -= 20;
    notes.push('Heavy rain expected');
  } else if (weather.precipitation > 1) {
    score -= 10;
    notes.push('Rain expected');
  }
  
  return { score: Math.max(0, Math.min(100, score)), notes };
}

/**
 * Score distance efficiency
 * Shorter routes get higher scores
 */
function scoreDistance(
  routeDistance: number,
  directDistance: number
): { score: number; notes: string[] } {
  const notes: string[] = [];
  const ratio = routeDistance / directDistance;
  
  let score = 100;
  if (ratio > 1.2) {
    score -= 20;
    notes.push(`${Math.round((ratio - 1) * 100)}% longer than direct route`);
  } else if (ratio > 1.1) {
    score -= 10;
    notes.push(`${Math.round((ratio - 1) * 100)}% longer than direct route`);
  } else if (ratio <= 1.02) {
    notes.push('Most direct path');
  }
  
  return { score, notes };
}

/**
 * Calculate bearing between consecutive waypoints
 */
function calculateSegmentBearings(waypoints: Waypoint[]): number[] {
  const bearings: number[] = [];
  for (let i = 0; i < waypoints.length - 1; i++) {
    bearings.push(
      calculateBearing(waypoints[i].position, waypoints[i + 1].position)
    );
  }
  return bearings;
}

/**
 * Main scoring function - scores a complete route
 */
export function scoreRoute(
  route: GeneratedRoute,
  boatType: string,
  directDistance: number
): Route {
  const boat = BOAT_PROFILES[boatType];
  const bearings = calculateSegmentBearings(route.waypoints);
  
  const allWarnings: string[] = [];
  const allPros: string[] = [];
  const allCons: string[] = [];
  
  let totalWindScore = 0;
  let totalWaveScore = 0;
  let totalVisibilityScore = 0;
  let segmentsScored = 0;
  
  // Score each waypoint/segment
  for (let i = 0; i < route.waypoints.length; i++) {
    const waypoint = route.waypoints[i];
    if (!waypoint.weather) continue;
    
    // Use the bearing of the segment starting at this waypoint
    const heading = bearings[Math.min(i, bearings.length - 1)] || 0;
    
    // Wind scoring
    const windResult = scoreWindConditions(waypoint.weather, heading, boat);
    totalWindScore += windResult.score;
    
    // Wave scoring
    const waveResult = scoreWaveConditions(waypoint.weather.waveHeight, boat);
    totalWaveScore += waveResult.score;
    
    // Visibility scoring
    const visResult = scoreVisibilityConditions(waypoint.weather);
    totalVisibilityScore += visResult.score;
    
    // Collect warnings (only unique ones)
    [...windResult.notes, ...waveResult.notes, ...visResult.notes].forEach((note) => {
      if (note.includes('Dangerous') || note.includes('exceeds')) {
        if (!allWarnings.includes(note)) allWarnings.push(note);
      }
    });
    
    segmentsScored++;
  }
  
  // Distance scoring
  const distanceResult = scoreDistance(route.distance, directDistance);
  
  // Calculate average scores
  const avgWindScore = segmentsScored > 0 ? totalWindScore / segmentsScored : 50;
  const avgWaveScore = segmentsScored > 0 ? totalWaveScore / segmentsScored : 50;
  const avgVisScore = segmentsScored > 0 ? totalVisibilityScore / segmentsScored : 50;
  
  // Weighted final score
  // Wind: 35%, Waves: 25%, Visibility: 15%, Distance: 25%
  const finalScore = Math.round(
    avgWindScore * 0.35 +
    avgWaveScore * 0.25 +
    avgVisScore * 0.15 +
    distanceResult.score * 0.25
  );
  
  // Generate pros and cons based on weather summary
  const weatherSummary = summarizeWeather(route.waypoints);
  
  // Pros
  if (weatherSummary.avgWindSpeed >= 8 && weatherSummary.avgWindSpeed <= 20) {
    allPros.push('Good sailing wind');
  }
  if (weatherSummary.avgWaveHeight < 1) {
    allPros.push('Calm seas');
  }
  if (!weatherSummary.hasRain) {
    allPros.push('No rain expected');
  }
  if (route.type === 'direct') {
    allPros.push('Shortest distance');
  }
  if (weatherSummary.avgVisibility > 15) {
    allPros.push('Excellent visibility');
  }
  
  // Cons
  if (weatherSummary.avgWindSpeed < 5 && boat.type === 'sailboat') {
    allCons.push('May need motor - low wind');
  }
  if (weatherSummary.maxWaveHeight > 2) {
    allCons.push('Rough sections expected');
  }
  if (weatherSummary.hasRain) {
    allCons.push('Rain expected on route');
  }
  if (route.distance > directDistance * 1.1) {
    allCons.push('Longer route');
  }
  
  return {
    name: route.name,
    type: route.type,
    score: Math.max(0, Math.min(100, finalScore)),
    distance: route.distance,
    estimatedTime: route.estimatedTime,
    estimatedHours: route.estimatedHours,
    waypoints: route.waypoints,
    warnings: allWarnings,
    pros: allPros.length > 0 ? allPros : ['Standard conditions'],
    cons: allCons.length > 0 ? allCons : ['No significant concerns'],
  };
}

