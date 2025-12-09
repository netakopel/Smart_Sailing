"""
AWS Lambda Handler for Smart Sailing Route Planner

This file wraps our existing code to work with AWS Lambda.
Lambda calls lambda_handler() with the request data.
"""

import json
from datetime import datetime

from models import RouteRequest, Coordinates, BoatType
from route_generator import generate_routes, calculate_distance
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route


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


def lambda_handler(event, context):
    """
    AWS Lambda entry point.
    
    Args:
        event: API Gateway request (contains body with JSON)
        context: Lambda context (runtime info, we don't use it)
        
    Returns:
        API Gateway response format
    """
    
    # CORS headers - needed for browser requests
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST, OPTIONS"
    }
    
    # Handle CORS preflight request
    # HTTP API v2 uses requestContext.http.method, REST API v1 uses httpMethod
    http_method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod")
    
    if http_method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }
    
    try:
        # Parse the request body
        # API Gateway sends body as string, we need to parse it
        if isinstance(event.get("body"), str):
            body = json.loads(event["body"])
        else:
            # Direct Lambda test or already parsed
            body = event.get("body") or event
        
        # Validate required fields
        required = ["start", "end", "boat_type", "departure_time"]
        for field in required:
            if field not in body:
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({"error": f"Missing required field: {field}"})
                }
        
        # Parse into our data types
        request = RouteRequest(
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
        
        # Step 1: Generate route options
        generated_routes = generate_routes(request)
        direct_distance = calculate_distance(request.start, request.end)
        
        # Step 2: Fetch weather for each route
        routes_with_weather = []
        for route in generated_routes:
            waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
            route.waypoints = waypoints_with_weather
            routes_with_weather.append(route)
        
        # Step 3: Score each route
        scored_routes = []
        for route in routes_with_weather:
            scored = score_route(route, request.boat_type, direct_distance)
            scored_routes.append(scored)
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda r: r.score, reverse=True)
        
        # Build response
        response_body = {
            "routes": [route_to_dict(r) for r in scored_routes],
            "calculatedAt": datetime.now().isoformat()
        }
        
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(response_body)
        }
        
    except ValueError as e:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": f"Invalid input: {str(e)}"})
        }
    except Exception as e:
        print(f"Error: {str(e)}")  # This goes to CloudWatch logs
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal server error"})
        }

