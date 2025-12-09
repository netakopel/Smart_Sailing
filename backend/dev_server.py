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
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route
from route_generator import calculate_distance

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
    
    This endpoint uses the NEW hybrid pattern-based routing algorithm!
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
        
        print(f"\n=== Calculating Routes (WIND-AWARE) ===")
        print(f"From: ({route_request.start.lat:.4f}, {route_request.start.lng:.4f})")
        print(f"To: ({route_request.end.lat:.4f}, {route_request.end.lng:.4f})")
        print(f"Boat: {route_request.boat_type.value}")
        
        # Step 1: Generate smart wind-aware routes
        print("\n[1] Generating wind-aware routes...")
        generated_routes = generate_hybrid_routes(route_request)
        print(f"   Generated {len(generated_routes)} routes")
        
        direct_distance = calculate_distance(route_request.start, route_request.end)
        
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
            print(f"   {scored.name}: {scored.score}/100")
            scored_routes.append(scored)
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda r: r.score, reverse=True)
        
        # Build response
        response_body = {
            "routes": [route_to_dict(r) for r in scored_routes],
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
    return jsonify({"status": "ok", "algorithm": "hybrid-wind-aware"}), 200


if __name__ == '__main__':
    print("=" * 60)
    print("  Smart Sailing Route Planner - Development Server")
    print("  Algorithm: WIND-AWARE HYBRID ROUTING")
    print("=" * 60)
    print("\n  Backend running on:  http://localhost:8000")
    print("  Frontend Vite proxy: /api -> http://localhost:8000")
    print("\n  Steps to run:")
    print("    1. Keep this terminal running")
    print("    2. Open new terminal: cd frontend && npm run dev")
    print("    3. Open browser: http://localhost:5173")
    print("\n" + "=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=8000, debug=True)

