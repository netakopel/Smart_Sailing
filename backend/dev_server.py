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
import os

from models import RouteRequest, Coordinates, BoatType, BOAT_PROFILES
# from wind_router import generate_hybrid_routes
from isochrone_router import generate_isochrone_routes
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route
from route_generator import calculate_distance  # , generate_routes

# Set up logging - both to file and console
# Use absolute path relative to project root (parent of backend/)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)  # Go up one level from backend/ to project root
log_file_path = os.path.join(project_root, 'backend.log')

# Clear any existing handlers to avoid conflicts
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)
    handler.close()

# Set up fresh handlers
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(log_format))

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(logging.Formatter(log_format))

root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
logger.info(f"Logging initialized - log file: {log_file_path}")

app = Flask(__name__)
CORS(app)  # Enable CORS for local development


def route_to_dict(route):
    """Convert Route object to dictionary for JSON response."""
    result = {
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
                "heading": wp.heading,  # Heading used to reach this waypoint (from previous waypoint)
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
    
    # Include no-go zone violations if present
    if hasattr(route, 'noGoZoneViolations') and route.noGoZoneViolations:  # type: ignore
        # Convert snake_case to camelCase for API
        result["noGoZoneViolations"] = [
            {
                "segmentIndex": v.get('segmentIndex') if isinstance(v, dict) else v['segmentIndex'],
                "heading": v.get('heading') if isinstance(v, dict) else v['heading'],
                "windAngle": v.get('windAngle') if isinstance(v, dict) else v['windAngle'],
            }
            for v in route.noGoZoneViolations  # type: ignore
        ]
    
    return result


@app.route('/calculate-routes', methods=['POST', 'OPTIONS'])
def calculate_routes():
    """
    Calculate smart wind-aware routes.
    
    Can use different algorithms based on 'algorithm' parameter:
    - 'isochrone' (default): Optimal isochrone algorithm
    - 'all': Run isochrone algorithm (same as 'isochrone')
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
        algorithm = body.get("algorithm", "isochrone")  # Default to isochrone algorithm
        
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
        weather_grid_metadata = {}  # Initialize for weather grid visualization
        
        # Handle deprecated algorithms
        if algorithm == "naive" or algorithm == "hybrid":
            logger.warning(f"   Algorithm '{algorithm}' is disabled. Using 'isochrone' instead.")
            algorithm = "isochrone"
        
        # if algorithm == "naive":
        #     # Simple geometric routes
        #     generated_routes = generate_routes(route_request)
        #     logger.info(f"   Generated {len(generated_routes)} naive routes")
        #     
        # elif algorithm == "hybrid":
        #     # Pattern-based wind routing
        #     generated_routes = generate_hybrid_routes(route_request)
        #     logger.info(f"   Generated {len(generated_routes)} hybrid routes")
        #     
        if algorithm == "isochrone":
            # Optimal isochrone algorithm
            weather_grid_metadata = {}
            try:
                generated_routes, weather_grid_metadata = generate_isochrone_routes(route_request)
                logger.info(f"   Generated {len(generated_routes)} isochrone routes")
                if not generated_routes:
                    logger.warning("   Isochrone algorithm returned 0 routes!")
            except Exception as e:
                logger.error(f"   ERROR in isochrone algorithm: {e}")
                traceback.print_exc()
                # Fallback to naive routes if isochrone fails
                # logger.info("   Falling back to naive routes...")
                # generated_routes = generate_routes(route_request)
                generated_routes = []  # No fallback - only isochrone
                weather_grid_metadata = {}
            
        elif algorithm == "all":
            # Run all algorithms and combine results
            logger.info("   Running isochrone algorithm only...")
            
            # Run naive routes
            # try:
            #     naive = generate_routes(route_request)
            #     logger.info(f"   - Naive: {len(naive)} routes")
            # except Exception as e:
            #     logger.error(f"   - Naive: FAILED ({e})")
            #     naive = []
            
            # Run hybrid routes
            # try:
            #     hybrid = generate_hybrid_routes(route_request)
            #     logger.info(f"   - Hybrid: {len(hybrid)} routes")
            # except Exception as e:
            #     logger.error(f"   - Hybrid: FAILED ({e})")
            #     hybrid = []
            
            # Add delay before isochrone to avoid API rate limits
            # import time
            # logger.info("   Waiting 3 seconds before isochrone (to avoid API rate limits)...")
            # time.sleep(3)
            
            # Run isochrone routes
            weather_grid_metadata = {}
            try:
                isochrone, weather_grid_metadata = generate_isochrone_routes(route_request)
                logger.info(f"   - Isochrone: {len(isochrone)} routes")
            except Exception as e:
                logger.error(f"   - Isochrone: FAILED ({e})")
                isochrone = []
                weather_grid_metadata = {}
            
            # Rename routes to show which algorithm generated them
            # for r in naive:
            #     r.name = f"[Naive] {r.name}"
            # for r in hybrid:
            #     r.name = f"[Hybrid] {r.name}"
            for r in isochrone:
                r.name = f"[Isochrone] {r.name}"
            
            # generated_routes = naive + hybrid + isochrone
            generated_routes = isochrone
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
            
            # Check for dangerous conditions (high wind/waves)
            # No-go zone checks are done later in the detailed validation
            dangerous_count = 0
            for i, wp in enumerate(waypoints_with_weather):
                if wp.weather:
                    # Check dangerous conditions (check for all route types)
                    if wp.weather.wind_speed > boat.max_safe_wind_speed:
                        dangerous_count += 1
                        logger.warning(f"      [DANGER] Wind: {wp.weather.wind_speed:.1f}kt (limit: {boat.max_safe_wind_speed}kt)")
                    if wp.weather.wave_height > boat.max_safe_wave_height:
                        dangerous_count += 1
                        logger.warning(f"      [DANGER] Waves: {wp.weather.wave_height:.1f}m (limit: {boat.max_safe_wave_height}m)")
            
            if dangerous_count > 0:
                logger.warning(f"      >>> {dangerous_count} DANGEROUS condition(s) detected!")
            
            route.waypoints = waypoints_with_weather
            routes_with_weather.append(route)
        
        # Step 2.5: Recalculate times for naive and hybrid routes based on actual wind conditions
        # (Isochrone routes already account for wind perfectly in their generation)
        logger.info("[2.5] Recalculating times with actual weather data...")
        # from route_generator import recalculate_route_times_with_wind
        routes_with_realistic_times = []
        for route in routes_with_weather:
            # if route.name.startswith("[Naive]") or route.name.startswith("[Hybrid]"):
            #     # Recalculate times using actual fetched weather (not interpolated grid)
            #     recalculated = recalculate_route_times_with_wind(
            #         route, 
            #         route_request.boat_type,
            #         datetime.fromisoformat(route_request.departure_time)
            #     )
            #     logger.info(f"   {route.name}: {route.estimated_hours:.1f}h -> {recalculated.estimated_hours:.1f}h")
            #     routes_with_realistic_times.append(recalculated)
            # else:
            # Isochrone routes already have realistic times based on actual propagation
            routes_with_realistic_times.append(route)
        
        # Step 3: Score each route
        logger.info("[3] Scoring routes...")
        scored_routes = []
        for route_idx, route in enumerate(routes_with_realistic_times):
            scored = score_route(route, route_request.boat_type, direct_distance)
            danger_indicator = " [DANGER!]" if any("DANGER" in w for w in scored.warnings) else ""
            logger.info(f"   {scored.name}: {scored.score}/100{danger_indicator}")
            if danger_indicator:
                danger_warnings = [w for w in scored.warnings if 'DANGER' in w]
                if danger_warnings:
                    logger.warning(f"      -> {danger_warnings[0]}")
            
            # Extract NO-GO zone violations from warnings for frontend
            # IMPORTANT: Use stored heading from propagation, not recalculated bearing
            # During isochrone propagation, headings are validated against no-go zones.
            # Recalculating bearings between waypoint positions can give different results
            # and falsely trigger no-go zone warnings. Always use the validated heading.
            no_go_violations = []
            logger.info(f"      Checking {len(scored.waypoints)} waypoints for no-go zone violations...")
            for i, wp in enumerate(scored.waypoints[:-1]):  # All but last waypoint
                if wp.weather:
                    from route_generator import calculate_bearing
                    from polars import is_in_no_go_zone, calculate_wind_angle
                    
                    # To check the segment FROM waypoint[i] TO waypoint[i+1]:
                    # - First try the heading stored at waypoint[i+1] (represents the leg arriving at i+1)
                    # - Fall back to calculating bearing between waypoints
                    next_wp = scored.waypoints[i+1]
                    
                    if next_wp.heading is not None:
                        heading = next_wp.heading
                        logger.debug(f"        WP{i}: Using STORED heading from NEXT waypoint: {heading:.1f}°")
                    else:
                        heading = calculate_bearing(wp.position, next_wp.position)
                        logger.debug(f"        WP{i}: CALCULATED heading: {heading:.1f}° (no stored heading at next WP)")
                    
                    wind_angle = calculate_wind_angle(heading, next_wp.weather.wind_direction)
                    logger.debug(f"        WP{i}: heading={heading:.1f}°, wind_from={next_wp.weather.wind_direction:.1f}°, wind_angle={wind_angle:.1f}°")
                    
                    if is_in_no_go_zone(wind_angle, route_request.boat_type.value):
                        logger.warning(f"        WP{i}: NO-GO ZONE VIOLATION! wind_angle={wind_angle:.1f}°")
                        no_go_violations.append({
                            'segmentIndex': i,
                            'heading': heading,
                            'windAngle': wind_angle
                        })
            
            # Attach violations to scored route
            if no_go_violations:
                scored.noGoZoneViolations = no_go_violations  # type: ignore
            
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
        
        # Add weather grid metadata if available (for visualization)
        if weather_grid_metadata and weather_grid_metadata.get('grid_points'):
            # Include hourly weather data if available
            response_body["weatherGrid"] = {
                "gridPoints": [
                    {"lat": lat, "lng": lng}
                    for lat, lng in weather_grid_metadata.get('grid_points', [])
                ],
                "bounds": weather_grid_metadata.get('bounds', {}),
                "times": weather_grid_metadata.get('times', []),
                "gridPointsWithWeather": weather_grid_metadata.get('gridPointsWithWeather', [])
            }
            logger.info(f"   Including weather grid: {len(response_body['weatherGrid']['gridPoints'])} points")
            if weather_grid_metadata.get('times'):
                logger.info(f"   Weather data for {len(weather_grid_metadata.get('times', []))} time steps")
        
        logger.info(f"[OK] Done! Returning {len(scored_routes)} scored routes")
        
        return jsonify(response_body), 200
        
    except ValueError as e:
        logger.error(f"[VALIDATION ERROR] {e}")
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[SERVER ERROR] {error_msg}")
        traceback.print_exc()
        
        # Check for rate limit issues
        if "429" in error_msg or "rate" in error_msg.lower():
            logger.error("[RATE LIMIT] API rate limit exceeded - Open-Meteo may have blocked this IP")
            return jsonify({
                "error": "API rate limit exceeded. Please try again in a few minutes.",
                "details": "Open-Meteo weather API blocked due to too many requests"
            }), 429
        
        # Check for timeout issues
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.error("[TIMEOUT] Request timed out during processing")
            return jsonify({
                "error": "Request timed out. Try with closer locations or simpler routes.",
                "details": "Processing took too long"
            }), 504
        
        return jsonify({"error": f"Server error: {error_msg}"}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "ok", 
        "algorithms": ["isochrone", "all"],  # ["naive", "hybrid", "isochrone", "all"],
        "default": "isochrone"
    }), 200


if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("  Smart Sailing Route Planner - Development Server")
    logger.info("=" * 70)
    logger.info("  MODE: Running ISOCHRONE algorithm only")
    logger.info("  Available Algorithms:")
    # logger.info("    * 'naive'     - Simple geometric routes")
    # logger.info("    * 'hybrid'    - Pattern-based wind routing")
    logger.info("    * 'isochrone' - Optimal isochrone algorithm [DEFAULT]")
    logger.info("    * 'all'       - Run isochrone algorithm (same as 'isochrone')")
    logger.info("  Backend running on:  http://localhost:8000")
    logger.info("  Frontend Vite proxy: /api -> http://localhost:8000")
    logger.info("  To test algorithms:")
    logger.info("    - Frontend will use 'isochrone' by default")
    logger.info("    - To test isochrone: Add {\"algorithm\": \"isochrone\"} to request")
    logger.info("    - Or use curl/Postman to test different algorithms")
    logger.info("  Steps to run:")
    logger.info("    1. Keep this terminal running")
    logger.info("    2. Open new terminal: cd frontend && npm run dev")
    logger.info("    3. Open browser: http://localhost:5173")
    logger.info("=" * 70)
    
    app.run(host='0.0.0.0', port=8000, debug=True)

