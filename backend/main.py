"""
Smart Sailing Route Planner - Main Entry Point

Run with: python main.py

This is the main script that ties everything together:
1. Takes a route request (start, end, boat type, departure time)
2. Generates 3 route options
3. Fetches real weather data for each route
4. Scores each route based on conditions
5. Returns recommendations sorted by score
"""

from datetime import datetime, timedelta
from typing import List
import json

from models import RouteRequest, RouteResponse, Route, Coordinates, BoatType
from route_generator import generate_routes, calculate_distance
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route


def calculate_routes(request: RouteRequest) -> RouteResponse:
    """
    Main function: Calculate routes between two points.
    
    Args:
        request: RouteRequest with start, end, boat_type, departure_time
        
    Returns:
        RouteResponse with 3 scored routes
    """
    print("\n=== Smart Sailing Route Planner ===")
    print("=" * 40)
    print(f"From: {request.start.lat:.4f}, {request.start.lng:.4f}")
    print(f"To: {request.end.lat:.4f}, {request.end.lng:.4f}")
    print(f"Boat: {request.boat_type.value}")
    print(f"Departure: {request.departure_time}")
    print()

    # Step 1: Generate route options
    print("[1] Generating routes...")
    generated_routes = generate_routes(request)
    
    direct_distance = calculate_distance(request.start, request.end)
    print(f"   Direct distance: {direct_distance:.1f} nm")

    # Step 2: Fetch weather for each route
    print("\n[2] Fetching weather data...")
    routes_with_weather = []
    for route in generated_routes:
        print(f"   {route.name}...")
        waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
        # Create new route with weather data
        route.waypoints = waypoints_with_weather
        routes_with_weather.append(route)

    # Step 3: Score each route
    print("\n[3] Scoring routes...")
    scored_routes: List[Route] = []
    for route in routes_with_weather:
        scored = score_route(route, request.boat_type, direct_distance)
        print(f"   {scored.name}: {scored.score}/100")
        scored_routes.append(scored)

    # Sort by score (highest first)
    scored_routes.sort(key=lambda r: r.score, reverse=True)

    return RouteResponse(
        routes=scored_routes,
        calculated_at=datetime.now().isoformat()
    )


def display_results(response: RouteResponse) -> None:
    """Display route results in a nice format."""
    print("\n")
    print("=" * 65)
    print("                    ROUTE RECOMMENDATIONS")
    print("=" * 65)

    medals = ["#1", "#2", "#3"]
    
    for i, route in enumerate(response.routes):
        medal = medals[i] if i < len(medals) else "  "
        
        print(f"\n{medal} {route.name.upper()}")
        print("-" * 40)
        print(f"   Score:      {route.score}/100")
        print(f"   Distance:   {route.distance} nm")
        print(f"   Duration:   {route.estimated_time}")
        
        if route.warnings:
            print("   [!] Warnings:")
            for w in route.warnings:
                print(f"      - {w}")
        
        print("   [+] Pros:")
        for p in route.pros:
            print(f"      - {p}")
        
        print("   [-] Cons:")
        for c in route.cons:
            print(f"      - {c}")
        
        # Show weather at start and middle waypoint
        midpoint = len(route.waypoints) // 2
        
        if route.waypoints[0].weather:
            w = route.waypoints[0].weather
            print("   Start conditions:")
            print(f"      Wind: {w.wind_speed}kt from {w.wind_direction} deg")
            print(f"      Waves: {w.wave_height}m | Temp: {w.temperature}C")
        
        if route.waypoints[midpoint].weather:
            w = route.waypoints[midpoint].weather
            print("   Mid-route conditions:")
            print(f"      Wind: {w.wind_speed}kt from {w.wind_direction} deg")
            print(f"      Waves: {w.wave_height}m | Temp: {w.temperature}C")

    print("\n" + "=" * 65)
    print(f"Calculated at: {response.calculated_at}")
    print("=" * 65 + "\n")


def route_to_dict(route: Route) -> dict:
    """Convert Route to dictionary for JSON output."""
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


def main():
    """
    Demo: Run with sample data.
    
    Example route: Southampton, UK to Cherbourg, France
    This is a classic English Channel crossing (~76 nautical miles)
    """
    
    # Create a route request
    # Southampton, UK to Cherbourg, France
    request = RouteRequest(
        start=Coordinates(lat=50.8965, lng=-1.3972),   # Southampton
        end=Coordinates(lat=49.6337, lng=-1.6222),     # Cherbourg
        boat_type=BoatType.SAILBOAT,
        departure_time=(datetime.now() + timedelta(days=1)).isoformat()  # Tomorrow
    )

    try:
        # Calculate routes
        response = calculate_routes(request)
        
        # Display nice formatted output
        display_results(response)
        
        # Also output JSON for API use
        print("\n--- JSON Response (for API use) ---")
        json_response = {
            "routes": [route_to_dict(r) for r in response.routes],
            "calculatedAt": response.calculated_at
        }
        print(json.dumps(json_response, indent=2))
        
    except Exception as e:
        print(f"Error calculating routes: {e}")
        raise


if __name__ == "__main__":
    main()

