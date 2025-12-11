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

from models import RouteRequest, Coordinates, BoatType
from wind_router import generate_hybrid_routes
from isochrone_router import generate_isochrone_routes
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route
from route_generator import calculate_distance, generate_routes

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
        
        print(f"\n=== Calculating Routes ===")
        print(f"Algorithm: {algorithm.upper()}")
        print(f"From: ({route_request.start.lat:.4f}, {route_request.start.lng:.4f})")
        print(f"To: ({route_request.end.lat:.4f}, {route_request.end.lng:.4f})")
        print(f"Boat: {route_request.boat_type.value}")
        
        # Step 1: Generate routes based on selected algorithm
        print(f"\n[1] Generating routes ({algorithm})...")
        generated_routes = []
        
        if algorithm == "naive":
            # Simple geometric routes
            generated_routes = generate_routes(route_request)
            print(f"   Generated {len(generated_routes)} naive routes")
            
        elif algorithm == "hybrid":
            # Pattern-based wind routing
            generated_routes = generate_hybrid_routes(route_request)
            print(f"   Generated {len(generated_routes)} hybrid routes")
            
        elif algorithm == "isochrone":
            # Optimal isochrone algorithm
            try:
                generated_routes = generate_isochrone_routes(route_request)
                print(f"   Generated {len(generated_routes)} isochrone routes")
                if not generated_routes:
                    print("   WARNING: Isochrone algorithm returned 0 routes!")
            except Exception as e:
                print(f"   ERROR in isochrone algorithm: {e}")
                traceback.print_exc()
                # Fallback to naive routes if isochrone fails
                print("   Falling back to naive routes...")
                generated_routes = generate_routes(route_request)
            
        elif algorithm == "all":
            # Run all algorithms and combine results
            print("   Running ALL algorithms...")
            
            # Run naive routes
            try:
                naive = generate_routes(route_request)
                print(f"   - Naive: {len(naive)} routes")
            except Exception as e:
                print(f"   - Naive: FAILED ({e})")
                naive = []
            
            # Run hybrid routes
            try:
                hybrid = generate_hybrid_routes(route_request)
                print(f"   - Hybrid: {len(hybrid)} routes")
            except Exception as e:
                print(f"   - Hybrid: FAILED ({e})")
                hybrid = []
            
            # Run isochrone routes
            try:
                isochrone = generate_isochrone_routes(route_request)
                print(f"   - Isochrone: {len(isochrone)} routes")
            except Exception as e:
                print(f"   - Isochrone: FAILED ({e})")
                isochrone = []
            
            # Rename routes to show which algorithm generated them
            for r in naive:
                r.name = f"[Naive] {r.name}"
            for r in hybrid:
                r.name = f"[Hybrid] {r.name}"
            for r in isochrone:
                r.name = f"[Isochrone] {r.name}"
            
            generated_routes = naive + hybrid + isochrone
            print(f"   Total: {len(generated_routes)} routes")
        else:
            return jsonify({"error": f"Unknown algorithm: {algorithm}"}), 400
        
        direct_distance = calculate_distance(route_request.start, route_request.end)
        
        # Check if we have any routes
        if not generated_routes:
            print("\n[ERROR] No routes generated!")
            return jsonify({"error": "No valid routes found"}), 500
        
        # Step 2: Fetch weather for each route (waypoints already have timing, just need weather data)
        print("\n[2] Fetching weather for waypoints...")
        routes_with_weather = []
        for route in generated_routes:
            print(f"   {route.name}: {len(route.waypoints)} waypoints...")
            waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
            route.waypoints = waypoints_with_weather
            routes_with_weather.append(route)
        
        # Step 3: Score each route
        print("\n[3] Scoring routes...")
        scored_routes = []
        for route in routes_with_weather:
            scored = score_route(route, route_request.boat_type, direct_distance)
            danger_indicator = " [DANGER!]" if any("DANGER" in w for w in scored.warnings) else ""
            print(f"   {scored.name}: {scored.score}/100{danger_indicator}")
            if danger_indicator:
                print(f"      -> {[w for w in scored.warnings if 'DANGER' in w][0]}")
            scored_routes.append(scored)
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda r: r.score, reverse=True)
        
        # Return only top 3 routes
        top_routes = scored_routes[:3]
        
        print(f"\n[OK] Returning top {len(top_routes)} routes (from {len(scored_routes)} total)")
        for i, route in enumerate(top_routes, 1):
            print(f"   #{i}: {route.name} - {route.score}/100")
        
        # Build response
        response_body = {
            "routes": [route_to_dict(r) for r in top_routes],
            "calculatedAt": datetime.now().isoformat()
        }
        
        print(f"\n[OK] Done! Returning {len(scored_routes)} scored routes\n")
        
        return jsonify(response_body), 200
        
    except ValueError as e:
        print(f"\n[✗] Validation error: {e}\n")
        return jsonify({"error": f"Invalid input: {str(e)}"}), 400
    except Exception as e:
        print(f"\n[✗] Server error: {e}")
        traceback.print_exc()
        print()
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
    print("=" * 70)
    print("  Smart Sailing Route Planner - Development Server")
    print("=" * 70)
    print("\n  MODE: Running ALL algorithms, returning best 3 routes")
    print("\n  Available Algorithms:")
    print("    * 'naive'     - Simple geometric routes")
    print("    * 'hybrid'    - Pattern-based wind routing")
    print("    * 'isochrone' - Optimal isochrone algorithm")
    print("    * 'all'       - Run all algorithms and compare [DEFAULT]")
    print("\n  Backend running on:  http://localhost:8000")
    print("  Frontend Vite proxy: /api -> http://localhost:8000")
    print("\n  To test algorithms:")
    print("    - Frontend will use 'naive' by default")
    print("    - To test isochrone: Add {\"algorithm\": \"isochrone\"} to request")
    print("    - Or use curl/Postman to test different algorithms")
    print("\n  Steps to run:")
    print("    1. Keep this terminal running")
    print("    2. Open new terminal: cd frontend && npm run dev")
    print("    3. Open browser: http://localhost:5173")
    print("\n" + "=" * 70 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=True)

