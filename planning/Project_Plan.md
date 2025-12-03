# Smart Sailing Route Planner - Project Plan

## Project Overview
A web application that helps sailors plan optimal routes based on weather forecasts and boat characteristics. Users input start/end locations and boat type, and the system analyzes weather data to recommend 3 route options with detailed pros/cons.

---

## Tech Stack

### Frontend
- React with TypeScript
- Leaflet (free, no API key required)
- Tailwind CSS for styling
- Deployed on AWS S3 + CloudFront

### Backend
- **Python** (we know it, it's standard for backends)
- AWS Lambda for serverless compute
- API Gateway for REST endpoint
- No database (stateless design - simpler)
- No caching (demo traffic won't hit API limits)

### Weather Data
- **Open-Meteo API** (completely free, no API key, no rate limits)
- Marine API for wave data
- Weather API for wind, temperature, visibility

---

## Architecture

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

**Simple request-response. No database, no caching, no queues.**

---

## Core Features

### 1. Route Generation
- Generate 3 route options between start and end points:
  - **Direct Route**: Shortest path (straight line)
  - **Northern Route**: Curves north (may have different weather)
  - **Southern Route**: Curves south (may have different weather)
- Calculate waypoints along each route (6 points)
- Use Haversine formula for accurate distance calculations

### 2. Weather Integration
- Fetch real weather data from Open-Meteo (free API)
- Get for each waypoint:
  - Wind speed and direction
  - Wave height
  - Temperature
  - Precipitation
  - Visibility

### 3. Route Scoring (0-100)
Score each route based on:
- **Wind conditions (35%)**: Good wind angle for sailing, safe wind speeds
- **Wave conditions (25%)**: Safe wave heights for boat type
- **Visibility (15%)**: Good visibility, no heavy rain
- **Distance efficiency (25%)**: Shorter is better

### 4. Boat Profiles
Different scoring for different boats:
- **Sailboat**: Needs wind (5-30 knots), wind angle matters
- **Motorboat**: Faster, less affected by wind
- **Catamaran**: Similar to sailboat, different limits

### 5. Frontend Visualization
- Interactive map with Leaflet
- Click to set start/end points
- Display all 3 routes in different colors
- Show weather conditions along routes
- Comparison cards for each route

---

## Implementation Phases

### Phase 1: Backend Algorithm (Days 1-3) ✅ DONE
Build the core logic locally in Python before any cloud setup.

- [x] Set up Python project structure
- [x] Create data models (`models.py`)
- [x] Implement route generation with Haversine formula (`route_generator.py`)
- [x] Integrate Open-Meteo weather API (`weather_fetcher.py`)
- [x] Build route scoring algorithm (`route_scorer.py`)
- [x] Create main entry point (`main.py`)
- [x] Test locally with sample coordinates

**Result**: Working Python code that calculates routes with real weather data.

### Phase 2: AWS Lambda Deployment (Days 4-5)
Wrap the Python code in a Lambda function and deploy.

- [ ] Create AWS account (if needed)
- [ ] Set up IAM roles for Lambda
- [ ] Create Lambda function with Python runtime
- [ ] Package dependencies (requests library)
- [ ] Create API Gateway endpoint
- [ ] Connect API Gateway to Lambda
- [ ] Test API endpoint with Postman/curl
- [ ] Handle CORS for frontend access

### Phase 3: Frontend Development (Days 6-9)
Build the React frontend with map and route display.

- [ ] Initialize React project with TypeScript
- [ ] Set up Tailwind CSS
- [ ] Integrate Leaflet map
- [ ] Build components:
  - [ ] `Map.tsx` - Interactive map with markers
  - [ ] `RouteForm.tsx` - Start/end selection, boat type picker
  - [ ] `RouteCards.tsx` - Display 3 routes with scores
  - [ ] `WeatherPanel.tsx` - Weather details for selected route
- [ ] Connect to backend API
- [ ] Handle loading states and errors
- [ ] Style for professional look

### Phase 4: Frontend Deployment (Day 10)
Deploy frontend to AWS.

- [ ] Build React app for production
- [ ] Create S3 bucket for static hosting
- [ ] Upload build files to S3
- [ ] Set up CloudFront CDN
- [ ] Configure HTTPS
- [ ] Test full end-to-end flow

### Phase 5: Polish & Testing (Days 11-12)
Make it interview-ready.

- [ ] Test with various routes (short, long, different regions)
- [ ] Handle edge cases
- [ ] Improve error messages
- [ ] Add loading animations
- [ ] Make responsive for mobile
- [ ] Performance optimization

### Phase 6: Documentation & Demo Prep (Days 13-14)
Prepare for interviews.

- [ ] Write comprehensive README with screenshots
- [ ] Document architecture decisions
- [ ] Prepare demo routes (impressive examples)
- [ ] Practice explaining the code
- [ ] Prepare answers for likely interview questions
- [ ] Optional: Record demo video

---

## Current File Structure

```
smart-sailing-planner/
├── planning/
│   ├── Project_Plan.md      # This file
│   └── High_Level_Design.md # Architecture decisions
│
├── backend/
│   ├── requirements.txt     # Python dependencies
│   ├── models.py           # Data classes (Route, Waypoint, etc.)
│   ├── route_generator.py  # Generate 3 route options
│   ├── weather_fetcher.py  # Fetch from Open-Meteo API
│   ├── route_scorer.py     # Score routes based on weather
│   └── main.py             # Entry point (will become Lambda handler)
│
├── frontend/               # To be created
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.tsx
│   │   │   ├── RouteForm.tsx
│   │   │   ├── RouteCards.tsx
│   │   │   └── WeatherPanel.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   └── App.tsx
│   └── package.json
│
├── .gitignore
└── README.md
```

---

## API Design

**Single endpoint:**

```
POST /api/calculate-routes

Request:
{
  "start": { "lat": 50.89, "lng": -1.39 },
  "end": { "lat": 49.63, "lng": -1.62 },
  "boat_type": "sailboat",
  "departure_time": "2024-01-15T08:00:00Z"
}

Response:
{
  "routes": [
    {
      "name": "Northern Route",
      "type": "northern",
      "score": 94,
      "distance": 79.3,
      "estimatedTime": "13h 13m",
      "waypoints": [...],
      "warnings": ["Dangerous wind: 49kt exceeds safe limit"],
      "pros": ["No rain expected", "Excellent visibility"],
      "cons": ["No significant concerns"]
    },
    // ... 2 more routes
  ],
  "calculatedAt": "2024-01-14T10:30:00Z"
}
```

---

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Backend language | Python | We know it, it's standard, works great with Lambda |
| Weather API | Open-Meteo | Free, no API key, no rate limits |
| Map library | Leaflet | Free, no API key (Mapbox charges after 50k loads) |
| Database | None | Stateless is simpler, no user accounts needed |
| Caching | None | Demo traffic won't hit API limits, fresh data is better |
| Hosting | S3 + CloudFront | Cheap, fast, handles HTTPS |

---

## Cost Estimate

| Service | Free Tier | Our Usage | Cost |
|---------|-----------|-----------|------|
| Lambda | 1M requests/month | ~100 | $0 |
| API Gateway | 1M requests/month | ~100 | $0 |
| S3 | 5GB storage | ~50MB | $0 |
| CloudFront | 1TB transfer | ~1GB | $0 |
| Open-Meteo | Unlimited | ~500 calls | $0 |
| **Total** | | | **$0** |

---

## Success Criteria

- [ ] User can select start/end points on a map
- [ ] System generates 3 distinct route recommendations
- [ ] Each route shows real weather conditions
- [ ] Routes are scored and ranked
- [ ] Beautiful, professional UI
- [ ] Fully deployed and accessible via URL
- [ ] Can explain every part of the code
- [ ] Ready for interview demos

---

## Interview Talking Points

**"Why Python for the backend?"**
> Python is standard for backends, works great with AWS Lambda, and I'm proficient in it. The choice of language matters less than the architecture decisions.

**"Why no database?"**
> Stateless by design. The app calculates routes from real-time weather data - there's nothing to store. If I needed user accounts or saved routes, I'd add DynamoDB.

**"Why no caching?"**
> For demo traffic, we won't hit API limits. Caching would add complexity and return stale weather data. In production with thousands of users, I'd add a DynamoDB cache with 1-hour TTL.

**"What was the hardest part?"**
> The route scoring algorithm. Balancing wind angle benefits against safety concerns required tuning the weights through testing with real weather scenarios.

**"How would you scale this?"**
> Lambda auto-scales. For global users, I'd deploy to multiple AWS regions. For heavy weather API usage, I'd add caching with TTL.

---

## Progress Tracker

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: Backend Algorithm | ✅ Done | Python code working locally |
| Phase 2: Lambda Deployment | ⬜ Not started | Next step |
| Phase 3: Frontend Development | ⬜ Not started | |
| Phase 4: Frontend Deployment | ⬜ Not started | |
| Phase 5: Polish & Testing | ⬜ Not started | |
| Phase 6: Documentation | ⬜ Not started | |

---

**Timeline:** 2 weeks (14 days)
**Current Status:** Phase 1 complete, ready for Phase 2
