# Smart Sailing Route Planner - High Level Design

## What We're Building
A web app where users pick start/end points on a map, select their boat type, and get 3 route recommendations with weather analysis.

---

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   React     │────▶│ API Gateway │────▶│   Lambda    │
│  Frontend   │     │             │     │  (Python)   │
│  (S3/CDN)   │◀────│             │◀────│             │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │ Open-Meteo  │
                                        │ Weather API │
                                        └─────────────┘
```

**That's it.** No database, no caching, no queues. Simple request-response.

---

## Technology Choices & Reasoning

### Frontend: React + TypeScript + Leaflet

| Choice | Why |
|--------|-----|
| **React** | Industry standard, interviewers expect it. Shows component thinking. |
| **TypeScript** | Demonstrates you write type-safe, maintainable code. Interviewers love it. |
| **Leaflet** | 100% free, no API key, no usage limits. Mapbox charges after 50k loads/month. |
| **Tailwind CSS** | Fast to style, looks professional, no CSS file management. |

### Backend: AWS Lambda + API Gateway

| Choice | Why |
|--------|-----|
| **Lambda (Python)** | Free tier = 1M requests/month. Zero server management. Python is standard and we know it. |
| **API Gateway** | Standard way to expose Lambda. Free tier = 1M requests/month. |
| **No Flask/EC2** | Why pay for a server that sits idle 99% of the time? Lambda is the right tool for sporadic demo traffic. |

### Weather API: Open-Meteo

| Choice | Why |
|--------|-----|
| **Open-Meteo** | Completely free, no API key, no rate limits, marine data available. |
| **NOT OpenWeatherMap** | Requires API key, 1000 calls/day limit, less marine-specific data. |

### Hosting: S3 + CloudFront

| Choice | Why |
|--------|-----|
| **S3** | Static hosting for React build. Pennies per month. |
| **CloudFront** | CDN for fast global delivery. Free tier = 1TB/month. HTTPS included. |

---

## What We're NOT Using (And Why)

| Skipped | Reason |
|---------|--------|
| **Database** | No user accounts, no saved routes. Stateless = simpler. If interviewer asks, say "I'd add DynamoDB for user features." |
| **Caching** | Demo traffic won't hit API limits. Fresh weather data is more valuable than cached. |
| **Docker/Kubernetes** | Overkill. Lambda handles deployment. Shows you don't over-engineer. |
| **Redis/ElastiCache** | No caching needed, adds cost and complexity. |

---

## Data Flow

```
1. User clicks start/end points on map
2. User selects boat type + departure time
3. Frontend sends POST /calculate-route
   {
     start: { lat, lng },
     end: { lat, lng },
     boatType: "sailboat",
     departureTime: "2024-01-15T08:00:00Z"
   }

4. Lambda receives request
5. Lambda generates 3 candidate routes (direct, northern, southern)
6. Lambda fetches weather for waypoints from Open-Meteo (parallel calls)
7. Lambda scores each route based on wind/waves/safety
8. Lambda returns 3 routes with scores and weather details

9. Frontend displays routes on map with comparison cards
```

---

## API Design

**Single endpoint. Keep it simple.**

```
POST /api/calculate-routes

Request:
{
  "start": { "lat": 51.5, "lng": -0.1 },
  "end": { "lat": 48.8, "lng": 2.3 },
  "boatType": "sailboat",
  "departureTime": "2024-01-15T08:00:00Z"
}

Response:
{
  "routes": [
    {
      "name": "Direct Route",
      "score": 72,
      "distance": 340,
      "estimatedTime": "18 hours",
      "waypoints": [...],
      "weather": [...],
      "warnings": ["High winds expected at waypoint 3"]
    },
    // ... 2 more routes
  ]
}
```

---

## Route Calculation Logic (High Level)

```
1. GENERATE ROUTES
   - Direct: straight line with 5-6 waypoints
   - Northern: arc 50km north of direct
   - Southern: arc 50km south of direct

2. FETCH WEATHER (for each waypoint)
   - Wind speed & direction
   - Wave height
   - Precipitation
   - Visibility

3. SCORE EACH ROUTE (0-100)
   - Wind angle bonus (sailing with wind = good)
   - High wind penalty (>25 knots = dangerous)
   - Wave height penalty (>2m = uncomfortable)
   - Storm penalty (heavy rain/low visibility)

4. RETURN sorted by score
```

---

## Cost Breakdown

| Service | Free Tier | Your Usage | Cost |
|---------|-----------|------------|------|
| Lambda | 1M requests/month | ~100 | $0 |
| API Gateway | 1M requests/month | ~100 | $0 |
| S3 | 5GB storage | ~50MB | $0 |
| CloudFront | 1TB transfer | ~1GB | $0 |
| Open-Meteo | Unlimited | ~500 calls | $0 |
| **Total** | | | **$0** |

---

## Interview Talking Points

**"Why serverless instead of a traditional server?"**
> For a sporadic-traffic app like this, Lambda is cost-effective and scales automatically. I'm not paying for idle compute. In high-traffic scenarios, I'd consider containers for predictable pricing.

**"Why no database?"**
> I kept it stateless intentionally. The app solves one problem: calculate routes from weather data. If I needed user accounts or saved routes, I'd add DynamoDB - it's serverless and fits the architecture.

**"How would you scale this?"**
> Lambda already auto-scales. For global users, I'd deploy to multiple regions. For heavy weather API usage, I'd add a DynamoDB cache with 1-hour TTL.

**"What was the hardest part?"**
> The route scoring algorithm. Balancing wind angle benefits for sailboats against safety concerns required tuning the weights through testing with real weather data.

---

## File Structure

```
smart-sailing-planner/
├── planning/
│   ├── Project_Plan.md           # Detailed project plan
│   └── High_Level_Design.md      # This file
│
├── backend/
│   ├── requirements.txt          # Python dependencies
│   ├── models.py                 # Data classes (Route, Waypoint, etc.)
│   ├── route_generator.py        # Generate 3 route options
│   ├── weather_fetcher.py        # Open-Meteo API calls
│   ├── route_scorer.py           # Score routes based on weather
│   └── main.py                   # Entry point / Lambda handler
│
├── frontend/                     # To be built
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.tsx           # Leaflet map with route display
│   │   │   ├── RouteForm.tsx     # Start/end/boat selection
│   │   │   ├── RouteCards.tsx    # Compare 3 routes
│   │   │   └── WeatherPanel.tsx  # Weather details for selected route
│   │   ├── services/
│   │   │   └── api.ts            # API client
│   │   └── App.tsx
│   └── package.json
│
└── README.md
```

---

## Summary

| Aspect | Decision |
|--------|----------|
| Complexity | Minimal - one Lambda, one endpoint, no DB |
| Cost | $0 (all free tiers) |
| Impressive? | Yes - clean architecture, real weather data, serverless AWS |
| Interview-ready? | Yes - easy to explain, clear tradeoffs documented |

