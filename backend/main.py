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
import logging

from models import RouteRequest, RouteResponse, Route, Coordinates, BoatType
from route_generator import generate_routes, calculate_distance
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_routes(request: RouteRequest) -> RouteResponse:
    """
    Main function: Calculate routes between two points.
    
    Args:
        request: RouteRequest with start, end, boat_type, departure_time
        
    Returns:
        RouteResponse with 3 scored routes
    """
    logger.info("\n=== Smart Sailing Route Planner ===")
    logger.info("=" * 40)
    logger.info(f"From: {request.start.lat:.4f}, {request.start.lng:.4f}")
    logger.info(f"To: {request.end.lat:.4f}, {request.end.lng:.4f}")
    logger.info(f"Boat: {request.boat_type.value}")
    logger.info(f"Departure: {request.departure_time}")
    logger.info()

    # Step 1: Generate route options
    logger.info("[1] Generating routes...")
    generated_routes = generate_routes(request)
    
    direct_distance = calculate_distance(request.start, request.end)
    logger.info(f"   Direct distance: {direct_distance:.1f} nm")

    # Step 2: Fetch weather for each route
    logger.info("\n[2] Fetching weather data...")
    routes_with_weather = []
    for route in generated_routes:
        logger.info(f"   {route.name}...")
        waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
        # Create new route with weather data
        route.waypoints = waypoints_with_weather
        routes_with_weather.append(route)

    # Step 3: Score each route
    logger.info("\n[3] Scoring routes...")
    scored_routes: List[Route] = []
    for route in routes_with_weather:
        scored = score_route(route, request.boat_type, direct_distance)
        logger.info(f"   {scored.name}: {scored.score}/100")
        scored_routes.append(scored)

    # Sort by score (highest first)
    scored_routes.sort(key=lambda r: r.score, reverse=True)

    return RouteResponse(
        routes=scored_routes,
        calculated_at=datetime.now().isoformat()
    )


def display_results(response: RouteResponse) -> None:
    """Display route results in a nice format."""
    logger.info("\n")
    logger.info("=" * 65)
    logger.info("                    ROUTE RECOMMENDATIONS")
    logger.info("=" * 65)

    medals = ["#1", "#2", "#3"]
    
    for i, route in enumerate(response.routes):
        medal = medals[i] if i < len(medals) else "  "
        
        logger.info(f"\n{medal} {route.name.upper()}")
        logger.info("-" * 40)
        logger.info(f"   Score:      {route.score}/100")
        logger.info(f"   Distance:   {route.distance} nm")
        logger.info(f"   Duration:   {route.estimated_time}")
        
        if route.warnings:
            logger.info("   [!] Warnings:")
            for w in route.warnings:
                logger.info(f"      - {w}")
        
        logger.info("   [+] Pros:")
        for p in route.pros:
            logger.info(f"      - {p}")
        
        logger.info("   [-] Cons:")
        for c in route.cons:
            logger.info(f"      - {c}")
        
        # Show weather at start and middle waypoint
        midpoint = len(route.waypoints) // 2
        
        if route.waypoints[0].weather:
            w = route.waypoints[0].weather
            logger.info("   Start conditions:")
            logger.info(f"      Wind: {w.wind_speed}kt (sustained {w.wind_sustained}kt, gusts {w.wind_gusts}kt)")
            logger.info(f"      Direction: {w.wind_direction} deg | Waves: {w.wave_height}m | Temp: {w.temperature}C")
        
        if route.waypoints[midpoint].weather:
            w = route.waypoints[midpoint].weather
            logger.info("   Mid-route conditions:")
            logger.info(f"      Wind: {w.wind_speed}kt (sustained {w.wind_sustained}kt, gusts {w.wind_gusts}kt)")
            logger.info(f"      Direction: {w.wind_direction} deg | Waves: {w.wave_height}m | Temp: {w.temperature}C")

    logger.info("\n" + "=" * 65)
    logger.info(f"Calculated at: {response.calculated_at}")
    logger.info("=" * 65 + "\n")


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


def main():
    """
    Demo: Run with sample data.
    
    Example route: Haifa, Israel to Limassol, Cyprus
    Mediterranean crossing (~180 nautical miles)
    """
    
    # Create a route request
    # Haifa, Israel to Limassol, Cyprus
    request = RouteRequest(
        start=Coordinates(lat=32.79, lng=34.99),   # Haifa, Israel
        end=Coordinates(lat=34.68, lng=33.04),     # Limassol, Cyprus
        boat_type=BoatType.SAILBOAT,
        departure_time=(datetime.now() + timedelta(days=1)).isoformat()  # Tomorrow
    )

    try:
        # Calculate routes
        response = calculate_routes(request)
        
        # Display nice formatted output
        display_results(response)
        
        # Also output JSON for API use
        logger.info("\n--- JSON Response (for API use) ---")
        json_response = {
            "routes": [route_to_dict(r) for r in response.routes],
            "calculatedAt": response.calculated_at
        }
        logger.info(json.dumps(json_response, indent=2))
        
    except Exception as e:
        logger.info(f"Error calculating routes: {e}")
        raise


if __name__ == "__main__":
    main()

