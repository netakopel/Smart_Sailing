import type { RouteRequest, RouteResponse } from '../types';

// In development, use Vite proxy (/api) to avoid CORS
// In production, use the direct AWS URL
const API_URL = import.meta.env.DEV 
  ? '/api' 
  : 'https://u2qvnjdj5m.execute-api.il-central-1.amazonaws.com';

export async function calculateRoutes(request: RouteRequest): Promise<RouteResponse> {
  // Add departure_time if not provided (required by backend)
  const requestWithTime = {
    ...request,
    departure_time: request.departure_time || new Date().toISOString(),
  };

  const response = await fetch(`${API_URL}/calculate-routes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(requestWithTime),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`API error: ${response.status} - ${errorBody}`);
  }

  return response.json();
}

