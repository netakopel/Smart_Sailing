"""
Local development server for the Smart Sailing Route Planner.

This wraps the Lambda function to work as a local HTTP server.
Run with: py -m uvicorn server:app --reload --port 8000
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import json

from lambda_function import lambda_handler

app = FastAPI(title="Smart Sailing Route Planner")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/calculate-routes")
async def calculate_routes(request: Request):
    """Forward request to Lambda handler."""
    body = await request.json()
    
    # Simulate Lambda event format
    event = {
        "httpMethod": "POST",
        "body": json.dumps(body)
    }
    
    # Call the Lambda handler
    result = lambda_handler(event, None)
    
    # Parse the response
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=result["statusCode"],
        content=json.loads(result["body"])
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

