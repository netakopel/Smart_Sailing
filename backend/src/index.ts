// Smart Sailing Route Planner - Main Entry Point
// Run with: npm run dev

import { RouteRequest, RouteResponse, Route } from './types';
import { generateRoutes } from './routeGenerator';
import { fetchWeatherForWaypoints } from './weatherFetcher';
import { scoreRoute } from './routeScorer';
import { calculateDistance } from './routeGenerator';

/**
 * Main function: Calculate routes between two points
 */
async function calculateRoutes(request: RouteRequest): Promise<RouteResponse> {
  console.log('\n🚤 Smart Sailing Route Planner');
  console.log('================================');
  console.log(`From: ${request.start.lat.toFixed(4)}, ${request.start.lng.toFixed(4)}`);
  console.log(`To: ${request.end.lat.toFixed(4)}, ${request.end.lng.toFixed(4)}`);
  console.log(`Boat: ${request.boatType}`);
  console.log(`Departure: ${new Date(request.departureTime).toLocaleString()}`);
  console.log('');

  // Step 1: Generate route options
  console.log('📍 Generating routes...');
  const generatedRoutes = generateRoutes(request);
  
  const directDistance = calculateDistance(request.start, request.end);
  console.log(`   Direct distance: ${directDistance.toFixed(1)} nm`);

  // Step 2: Fetch weather for each route
  console.log('\n🌤️  Fetching weather data...');
  const routesWithWeather = await Promise.all(
    generatedRoutes.map(async (route) => {
      console.log(`   ${route.name}...`);
      const waypointsWithWeather = await fetchWeatherForWaypoints(route.waypoints);
      return { ...route, waypoints: waypointsWithWeather };
    })
  );

  // Step 3: Score each route
  console.log('\n📊 Scoring routes...');
  const scoredRoutes: Route[] = routesWithWeather.map((route) => {
    const scored = scoreRoute(route, request.boatType, directDistance);
    console.log(`   ${scored.name}: ${scored.score}/100`);
    return scored;
  });

  // Sort by score (highest first)
  scoredRoutes.sort((a, b) => b.score - a.score);

  return {
    routes: scoredRoutes,
    calculatedAt: new Date().toISOString(),
  };
}

/**
 * Display route results in a nice format
 */
function displayResults(response: RouteResponse): void {
  console.log('\n');
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('                        ROUTE RECOMMENDATIONS');
  console.log('═══════════════════════════════════════════════════════════════');

  response.routes.forEach((route, index) => {
    const medal = index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉';
    
    console.log(`\n${medal} ${route.name.toUpperCase()}`);
    console.log('───────────────────────────────────────');
    console.log(`   Score:      ${route.score}/100`);
    console.log(`   Distance:   ${route.distance} nm`);
    console.log(`   Duration:   ${route.estimatedTime}`);
    
    if (route.warnings.length > 0) {
      console.log(`   ⚠️  Warnings:`);
      route.warnings.forEach((w) => console.log(`      - ${w}`));
    }
    
    console.log(`   ✅ Pros:`);
    route.pros.forEach((p) => console.log(`      - ${p}`));
    
    console.log(`   ❌ Cons:`);
    route.cons.forEach((c) => console.log(`      - ${c}`));
    
    // Show weather at first and middle waypoint
    const midpoint = Math.floor(route.waypoints.length / 2);
    if (route.waypoints[0]?.weather) {
      const startWeather = route.waypoints[0].weather;
      console.log(`   🌊 Start conditions:`);
      console.log(`      Wind: ${startWeather.windSpeed}kt from ${startWeather.windDirection}°`);
      console.log(`      Waves: ${startWeather.waveHeight}m | Temp: ${startWeather.temperature}°C`);
    }
    if (route.waypoints[midpoint]?.weather) {
      const midWeather = route.waypoints[midpoint].weather;
      console.log(`   🌊 Mid-route conditions:`);
      console.log(`      Wind: ${midWeather.windSpeed}kt from ${midWeather.windDirection}°`);
      console.log(`      Waves: ${midWeather.waveHeight}m | Temp: ${midWeather.temperature}°C`);
    }
  });

  console.log('\n═══════════════════════════════════════════════════════════════');
  console.log(`Calculated at: ${new Date(response.calculatedAt).toLocaleString()}`);
  console.log('═══════════════════════════════════════════════════════════════\n');
}

// ============================================================================
// DEMO: Run with sample data
// ============================================================================

async function main() {
  // Example: Southampton, UK to Cherbourg, France (Classic cross-channel route)
  const request: RouteRequest = {
    start: { lat: 50.8965, lng: -1.3972 },  // Southampton, UK
    end: { lat: 49.6337, lng: -1.6222 },    // Cherbourg, France
    boatType: 'sailboat',
    departureTime: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), // Tomorrow
  };

  try {
    const response = await calculateRoutes(request);
    displayResults(response);
    
    // Also output JSON for debugging/API use
    console.log('\n📄 JSON Response (for API use):');
    console.log(JSON.stringify(response, null, 2));
    
  } catch (error) {
    console.error('Error calculating routes:', error);
    process.exit(1);
  }
}

// Run the demo
main();

// Export for use as a module (e.g., in Lambda)
export { calculateRoutes };

