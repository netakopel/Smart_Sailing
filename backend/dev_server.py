"""
Local Development Server for Smart Sailing Route Planner

Run this to test the frontend locally:
1. Terminal 1: python backend/dev_server.py
2. Terminal 2: cd frontend && npm run dev
3. Open browser: http://localhost:5173

This uses the NEW wind-aware routing algorithm!
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import traceback
import logging

from models import RouteRequest, Coordinates, BoatType, BOAT_PROFILES
from wind_router import generate_hybrid_routes
from isochrone_router import generate_isochrone_routes
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route
from route_generator import calculate_distance, generate_routes

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for local development


def route_to_dict(route):
    """Convert Route object to dictionary for JSON response."""
    return {
        "name": route.name,
        "type": route.route_type.value,
        "score": route.score,
        "distance": route.distance,
        "estimatedTime": route.estimated_time,
        "estimatedHours": route.estimated_hours,
        "waypoints": [
            {
                "position": {"lat": wp.position.lat, "lng": wp.position.lng},
                "estimatedArrival": wp.estimated_arrival,
                "weather": {
                    "windSpeed": wp.weather.wind_speed,
                    "windSustained": wp.weather.wind_sustained,
                    "windGusts": wp.weather.wind_gusts,
                    "windDirection": wp.weather.wind_direction,
                    "waveHeight": wp.weather.wave_height,
                    "precipitation": wp.weather.precipitation,
                    "visibility": wp.weather.visibility,
                    "temperature": wp.weather.temperature
                } if wp.weather else None
            }
            for wp in route.waypoints
        ],
        "warnings": route.warnings,
        "pros": route.pros,
        "cons": route.cons
    }


@app.route('/calculate-routes', methods=['POST', 'OPTIONS'])
def calculate_routes():
    """
    Calculate smart wind-aware routes.
    
    Can use different algorithms based on 'algorithm' parameter:
    - 'naive' (default): Simple geometric routes
    - 'hybrid': Pattern-based wind routing
    - 'isochrone': Optimal isochrone algorithm
    - 'all': Run all algorithms and return combined results
    """
    
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        return '', 200
    
    try:
        body = request.json
        
        # Validate required fields
        required = ["start", "end", "boat_type", "departure_time"]
        for field in required:
            if field not in body:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Optional: algorithm selection
        algorithm = body.get("algorithm", "all")  # Default to all algorithms
        
        # Parse into our data types
        route_request = RouteRequest(
            start=Coordinates(
                lat=float(body["start"]["lat"]),
                lng=float(body["start"]["lng"])
            ),
            end=Coordinates(
                lat=float(body["end"]["lat"]),
                lng=float(body["end"]["lng"])
            ),
            boat_type=BoatType(body["boat_type"]),
            departure_time=body["departure_time"]
        )
        
        logger.info("=== Calculating Routes ===")
        logger.info(f"Algorithm: {algorithm.upper()}")
        logger.info(f"From: ({route_request.start.lat:.4f}, {route_request.start.lng:.4f})")
        logger.info(f"To: ({route_request.end.lat:.4f}, {route_request.end.lng:.4f})")
        logger.info(f"Boat: {route_request.boat_type.value}")
        
        # Step 1: Generate routes based on selected algorithm
        logger.info(f"[1] Generating routes ({algorithm})...")
        generated_routes = []
        
        if algorithm == "naive":
            # Simple geometric routes
            generated_routes = generate_routes(route_request)
            logger.info(f"   Generated {len(generated_routes)} naive routes")
            
        elif algorithm == "hybrid":
            # Pattern-based wind routing
            generated_routes = generate_hybrid_routes(route_request)
            logger.info(f"   Generated {len(generated_routes)} hybrid routes")
            
        elif algorithm == "isochrone":
            # Optimal isochrone algorithm
            try:
                generated_routes = generate_isochrone_routes(route_request)
                logger.info(f"   Generated {len(generated_routes)} isochrone routes")
                if not generated_routes:
                    logger.warning("   Isochrone algorithm returned 0 routes!")
            except Exception as e:
                logger.error(f"   ERROR in isochrone algorithm: {e}")
                traceback.print_exc()
                # Fallback to naive routes if isochrone fails
                logger.info("   Falling back to naive routes...")
                generated_routes = generate_routes(route_request)
            
        elif algorithm == "all":
            # Run all algorithms and combine results
            logger.info("   Running ALL algorithms...")
            
            # Run naive routes
            try:
                naive = generate_routes(route_request)
                logger.info(f"   - Naive: {len(naive)} routes")
            except Exception as e:
                logger.error(f"   - Naive: FAILED ({e})")
                naive = []
            
            # Run hybrid routes
            try:
                hybrid = generate_hybrid_routes(route_request)
                logger.info(f"   - Hybrid: {len(hybrid)} routes")
            except Exception as e:
                logger.error(f"   - Hybrid: FAILED ({e})")
                hybrid = []
            
            # Run isochrone routes
            try:
                isochrone = generate_isochrone_routes(route_request)
                logger.info(f"   - Isochrone: {len(isochrone)} routes")
            except Exception as e:
                logger.error(f"   - Isochrone: FAILED ({e})")
                isochrone = []
            
            # Rename routes to show which algorithm generated them
            for r in naive:
                r.name = f"[Naive] {r.name}"
            for r in hybrid:
                r.name = f"[Hybrid] {r.name}"
            for r in isochrone:
                r.name = f"[Isochrone] {r.name}"
            
            generated_routes = naive + hybrid + isochrone
            logger.info(f"   Total: {len(generated_routes)} routes")
        else:
            return jsonify({"error": f"Unknown algorithm: {algorithm}"}), 400
        
        direct_distance = calculate_distance(route_request.start, route_request.end)
        
        # Check if we have any routes
        if not generated_routes:
            logger.error("No routes generated!")
            return jsonify({"error": "No valid routes found"}), 500
        
        # Step 2: Fetch weather for each route (waypoints already have timing, just need weather data)
        logger.info("[2] Fetching weather for waypoints...")
        boat = BOAT_PROFILES[route_request.boat_type]
        routes_with_weather = []
        for route in generated_routes:
            logger.info(f"   {route.name}: {len(route.waypoints)} waypoints...")
            waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
            
            # Check for no-go zones and dangerous conditions
            # Skip no-go zone check for Isochrone routes (they already avoid no-go zones by design)
            no_go_count = 0
            dangerous_count = 0
            for i, wp in enumerate(waypoints_with_weather):
                if wp.weather:
                    # Check if sailing into wind (no-go zone) - skip for Isochrone routes
                    if i < len(waypoints_with_weather) - 1 and not route.name.startswith("[Isochrone]"):
                        from route_generator import calculate_bearing
                        from polars import is_in_no_go_zone, calculate_wind_angle
                        
                        heading = calculate_bearing(wp.position, waypoints_with_weather[i+1].position)
                        wind_angle = calculate_wind_angle(heading, wp.weather.wind_direction)
                        
                        if is_in_no_go_zone(wind_angle, boat.boat_type.value):
                            no_go_count += 1
                            logger.warning(f"      [NO-GO] Wind angle: {wind_angle:.0f}° (sailing into wind!)")
                    
                    # Check dangerous conditions (check for all route types)
                    if wp.weather.wind_speed > boat.max_safe_wind_speed:
                        dangerous_count += 1
                        logger.warning(f"      [DANGER] Wind: {wp.weather.wind_speed:.1f}kt (limit: {boat.max_safe_wind_speed}kt)")
                    if wp.weather.wave_height > boat.max_safe_wave_height:
                        dangerous_count += 1
                        logger.warning(f"      [DANGER] Waves: {wp.weather.wave_height:.1f}m (limit: {boat.max_safe_wave_height}m)")
            
            if no_go_count > 0:
                logger.warning(f"      >>> {no_go_count} NO-GO ZONE waypoint(s) detected!")
            if dangerous_count > 0:
                logger.warning(f"      >>> {dangerous_count} DANGEROUS condition(s) detected!")
            
            route.waypoints = waypoints_with_weather
            routes_with_weather.append(route)
        
        # Step 2.5: Recalculate times for naive and hybrid routes based on actual wind conditions
        # (Isochrone routes already account for wind perfectly in their generation)
        logger.info("[2.5] Recalculating times with actual weather data...")
        from route_generator import recalculate_route_times_with_wind
        routes_with_realistic_times = []
        for route in routes_with_weather:
            if route.name.startswith("[Naive]") or route.name.startswith("[Hybrid]"):
                # Recalculate times using actual fetched weather (not interpolated grid)
                recalculated = recalculate_route_times_with_wind(
                    route, 
                    route_request.boat_type,
                    datetime.fromisoformat(route_request.departure_time)
                )
                logger.info(f"   {route.name}: {route.estimated_hours:.1f}h -> {recalculated.estimated_hours:.1f}h")
                routes_with_realistic_times.append(recalculated)
            else:
                # Isochrone routes already have realistic times based on actual propagation
                routes_with_realistic_times.append(route)
        
        # Step 3: Score each route
        logger.info("[3] Scoring routes...")
        scored_routes = []
        for route in routes_with_realistic_times:
            scored = score_route(route, route_request.boat_type, direct_distance)
            danger_indicator = " [DANGER!]" if any("DANGER" in w for w in scored.warnings) else ""
            logger.info(f"   {scored.name}: {scored.score}/100{danger_indicator}")
            if danger_indicator:
                danger_warnings = [w for w in scored.warnings if 'DANGER' in w]
                if danger_warnings:
                    logger.warning(f"      -> {danger_warnings[0]}")
            scored_routes.append(scored)
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda r: r.score, reverse=True)
        
        # Show ALL scores
        logger.info("[ALL ROUTES RANKED]:")
        for i, route in enumerate(scored_routes, 1):
            logger.info(f"   #{i}: {route.name} - {route.score}/100")
        
        # Return ALL routes (not just top 3)
        top_routes = scored_routes  # Changed to show all routes
        
        logger.info(f"[OK] Returning all {len(top_routes)} routes")
        
        # Build response
        response_body = {
            "routes": [route_to_dict(r) for r in top_routes],
            "calculatedAt": datetime.now().isoformat()
        }
        
        logger.info(f"[OK] Done! Returning {len(scored_routes)} scored routes")
        
        return jsonify(response_body), 200
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        logger.error(f"Server error: {e}")
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok", 
        "algorithms": ["naive", "hybrid", "isochrone", "all"],
        "default": "naive"
    }), 200


if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("  Smart Sailing Route Planner - Development Server")
    logger.info("=" * 70)
    logger.info("  MODE: Running ALL algorithms, returning best 3 routes")
    logger.info("  Available Algorithms:")
    logger.info("    * 'naive'     - Simple geometric routes")
    logger.info("    * 'hybrid'    - Pattern-based wind routing")
    logger.info("    * 'isochrone' - Optimal isochrone algorithm")
    logger.info("    * 'all'       - Run all algorithms and compare [DEFAULT]")
    logger.info("  Backend running on:  http://localhost:8000")
    logger.info("  Frontend Vite proxy: /api -> http://localhost:8000")
    logger.info("  To test algorithms:")
    logger.info("    - Frontend will use 'naive' by default")
    logger.info("    - To test isochrone: Add {\"algorithm\": \"isochrone\"} to request")
    logger.info("    - Or use curl/Postman to test different algorithms")
    logger.info("  Steps to run:")
    logger.info("    1. Keep this terminal running")
    logger.info("    2. Open new terminal: cd frontend && npm run dev")
    logger.info("    3. Open browser: http://localhost:5173")
    logger.info("=" * 70)
    
    app.run(host='0.0.0.0', port=8000, debug=True)

