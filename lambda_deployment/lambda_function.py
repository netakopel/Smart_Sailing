"""
AWS Lambda Handler for Smart Sailing Route Planner

This file wraps our existing code to work with AWS Lambda.
Lambda calls lambda_handler() with the request data.
"""

import json
import logging
import traceback
from datetime import datetime

from models import RouteRequest, Coordinates, BoatType
from route_generator import generate_routes, calculate_distance
from isochrone_router import generate_isochrone_routes
from weather_fetcher import fetch_weather_for_waypoints
from route_scorer import score_route

# Set up logging (Lambda logs to CloudWatch)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)  # Capture DEBUG messages for troubleshooting


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
        
        logger.info(f"[REQUEST] Route from ({request.start.lat:.2f}, {request.start.lng:.2f}) "
                   f"to ({request.end.lat:.2f}, {request.end.lng:.2f}) | "
                   f"Boat: {request.boat_type.value} | Departure: {request.departure_time}")
        
        # Step 1: Generate route options using ISOCHRONE algorithm
        logger.info("[STEP 1] Generating routes using Isochrone algorithm...")
        generated_routes = generate_isochrone_routes(request)
        logger.info(f"[STEP 1 OK] Generated {len(generated_routes)} route(s)")
        
        if not generated_routes:
            logger.warning("[STEP 1] No routes generated, trying fallback...")
            generated_routes = generate_routes(request)
            logger.info(f"[STEP 1 FALLBACK] Generated {len(generated_routes)} fallback route(s)")
        
        direct_distance = calculate_distance(request.start, request.end)
        logger.info(f"[INFO] Direct distance: {direct_distance:.2f} nm")
        
        # Step 2: Fetch weather for each route
        # This step makes API calls - this is where rate limiting can occur
        logger.info(f"[STEP 2] Fetching weather for {len(generated_routes)} route(s) "
                   f"({len(generated_routes) * 2} API calls)...")
        routes_with_weather = []
        for i, route in enumerate(generated_routes):
            logger.debug(f"[STEP 2] Route {i+1}/{len(generated_routes)}: "
                        f"Fetching weather for {len(route.waypoints)} waypoints...")
            waypoints_with_weather = fetch_weather_for_waypoints(route.waypoints)
            route.waypoints = waypoints_with_weather
            routes_with_weather.append(route)
        logger.info(f"[STEP 2 OK] Weather fetched for all routes")
        
        # Step 3: Score each route
        logger.info("[STEP 3] Scoring routes...")
        scored_routes = []
        for route in routes_with_weather:
            scored = score_route(route, request.boat_type, direct_distance)
            scored_routes.append(scored)
        logger.info(f"[STEP 3 OK] Scored {len(scored_routes)} route(s)")
        
        # Sort by score (highest first)
        scored_routes.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"[SORTED] Best route score: {scored_routes[0].score if scored_routes else 'N/A'}")
        
        # Build response
        response_body = {
            "routes": [route_to_dict(r) for r in scored_routes],
            "calculatedAt": datetime.now().isoformat()
        }
        
        logger.info(f"[SUCCESS] Returning {len(scored_routes)} routes to client")
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(response_body)
        }
        
    except ValueError as e:
        logger.warning(f"[VALIDATION ERROR] {str(e)}")
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": f"Invalid input: {str(e)}"})
        }
    except Exception as e:
        # Detailed error logging for CloudWatch
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        
        logger.error(f"[LAMBDA ERROR] {error_msg}")
        logger.error(f"[STACK TRACE]\n{stack_trace}")
        
        # Check if this is a rate limit issue
        if "429" in error_msg or "rate" in error_msg.lower():
            logger.error("[RATE LIMIT] Detected rate limiting issue - API may be temporarily blocked")
            return {
                "statusCode": 429,
                "headers": headers,
                "body": json.dumps({"error": "API rate limit exceeded. Please try again in a few minutes."})
            }
        
        # Check if this is a timeout
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            logger.error("[TIMEOUT] Request took too long to process")
            return {
                "statusCode": 504,
                "headers": headers,
                "body": json.dumps({"error": "Request timed out. Please try with closer waypoints or simpler routes."})
            }
        
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": "Internal server error. Check logs for details."})
        }

