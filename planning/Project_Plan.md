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

### Phase 1: Backend Algorithm - Naive Version (Days 1-3) ✅ DONE
Build the core logic locally in Python before any cloud setup.
Uses a simple "generate-then-evaluate" approach: creates 3 geometric route alternatives (direct, port curve, starboard curve) without considering wind data, then scores them after fetching weather.

- [x] Set up Python project structure
- [x] Create data models (`models.py`)
- [x] Implement route generation with Haversine formula (`route_generator.py`)
- [x] Integrate Open-Meteo weather API (`weather_fetcher.py`)
- [x] Build route scoring algorithm (`route_scorer.py`)
- [x] Create main entry point (`main.py`)
- [x] Test locally with sample coordinates

**Result**: Working Python code that calculates routes with real weather data.
**Note**: This is a naive algorithm - routes are generated geometrically without wind optimization. See Phase 7 for planned improvements.

### Phase 2: AWS Lambda Deployment (Days 4-5)
Wrap the Python code in a Lambda function and deploy.

#### Step 2.1: Create AWS Account ✅
- [x] Go to aws.amazon.com and create a free account
- [x] Set up billing alerts (Zero spend budget created)
- [ ] Enable MFA (Multi-Factor Authentication) for security (optional, skip for now)

#### Step 2.2: Understand AWS Console ✅
- [x] Log into AWS Console
- [x] Learn to navigate to Lambda and API Gateway services
- [x] Understand the region selector (Israel/Tel Aviv selected)

#### Step 2.3: Create Lambda Function ✅
- [x] Navigate to Lambda service
- [x] Create new function `sailing-route-planner` with Python 3.11 runtime
- [x] Understand the Lambda code editor (tested with Hello World)

#### Step 2.4: Adapt Code for Lambda ✅
- [x] Create `lambda_handler` function (AWS Lambda's entry point)
- [x] Handle JSON input/output format
- [x] Package dependencies (requests library) into a deployment ZIP
- [x] Upload ZIP to Lambda and test successfully

#### Step 2.5: Create API Gateway ✅
- [x] Create HTTP API in API Gateway (`sailing-api`)
- [x] Create POST route `/calculate-routes`
- [x] Connect route to Lambda function
- [x] CORS headers added in Lambda code

#### Step 2.6: Test & Verify ✅
- [x] Test Lambda function directly in AWS Console
- [x] Test API endpoint with PowerShell - SUCCESS!
- [x] Verify full end-to-end flow

**API Endpoint:** `https://u2qvnjdj5m.execute-api.il-central-1.amazonaws.com/calculate-routes`

### Phase 3: Frontend Development (Days 6-9) ✅ DONE
Build the React frontend with map and route display.

- [x] Initialize React project with TypeScript (Vite)
- [x] Set up Tailwind CSS (dark nautical theme)
- [x] Integrate Leaflet map (react-leaflet with CartoDB dark tiles)
- [x] Build components:
  - [x] `Map.tsx` - Interactive map with click-to-set markers, route polylines
  - [x] `RouteForm.tsx` - Boat type selector, step-by-step guidance
  - [x] `RouteCards.tsx` - Display 3 routes with scores, warnings, pros/cons
  - [x] `WeatherPanel.tsx` - Weather details for selected route
- [x] Connect to backend API (with Vite proxy for CORS in dev)
- [x] Handle loading states and errors
- [x] Style for professional look

**Result**: Beautiful, fully functional React frontend connected to Lambda backend.
**Dev Server**: `npm run dev` → http://localhost:5173

### Phase 4: Frontend Deployment (Day 10) ✅ DONE
Deploy frontend to AWS.

- [x] Build React app for production (`npm run build` → `dist/` folder)
- [x] Create S3 bucket for static hosting (`smart-sailing-planner-frontend`)
- [x] Upload build files to S3
- [x] Set up CloudFront CDN
- [x] Configure HTTPS (automatic with CloudFront)
- [x] Test full end-to-end flow

**Production URL:** `https://d2zb6habqv1546.cloudfront.net`
**S3 Bucket:** `smart-sailing-planner-frontend`
**CloudFront Distribution:** `d2zb6habqv1546.cloudfront.net`

### Phase 5: Smart Route Algorithm (Days 11-20)
Now that the full system is working end-to-end, implement TWO wind-aware algorithms that work together:
1. **Hybrid Pattern-Based** - Fast, uses sailing tactics (tacking, VMG optimization)
2. **Isochrone Optimization** - Slower, finds mathematically optimal path

**Strategy**: Run both algorithms, score all generated routes, return the top 3 to the user.

#### Phase 5A: Foundation & Hybrid Algorithm (Days 11-14)
- [ ] Create `backend/polars.py` with polar diagram data and interpolation functions
  - Define simplified polar tables for each boat type
  - Implement bilinear interpolation: `get_boat_speed(wind_speed, wind_angle, boat_type)`
  - Calculate optimal VMG angles for each boat type
- [ ] Add regional weather grid fetching to `backend/weather_fetcher.py`
  - New function: `fetch_regional_weather_grid(bounds, departure_time)`
  - Get weather for entire route area (not just waypoints)
  - Simple 2D grid for interpolation at arbitrary points
- [ ] Create `backend/wind_router.py` for wind pattern analysis and scenario classification
  - Analyze prevailing winds along route corridor
  - Classify sailing scenario (upwind/downwind/beam reach)
  - Detect no-go zones
- [ ] Build hybrid pattern-based route generator in `wind_router.py`
  - **Tacking route** (if upwind): Zigzag at optimal VMG angle
  - **VMG-optimized route**: Follow best sailing angles
  - **Weather-seeking route**: Curve toward favorable winds
  - Return 3 routes in standard format

#### Phase 5B: Isochrone Algorithm (Days 15-19)
- [ ] Create `backend/isochrone_router.py` with core isochrone propagation
  - Implement time-based forward propagation
  - Try all possible headings at each step (e.g., every 10°)
  - Calculate boat speed using polars + weather at each point
- [ ] Add pruning and path reconstruction for isochrones
  - Prune dominated solutions (keep only Pareto-optimal points)
  - Trace back optimal path from destination to start
  - Generate 2-3 route variations (fastest, safest)
  - Optimize: adaptive time step, angular resolution tuning

#### Phase 5C: Integration & Testing (Day 20)
- [ ] Wire both algorithms in `lambda_function.py`
  - Run both hybrid AND isochrone algorithms
  - Collect all generated routes (5-6 total)
  - Score all routes using existing `route_scorer.py`
  - Sort by score and return top 3
- [ ] Test both algorithms on varied scenarios and compare results
  - Short route (50nm) uniform wind → Expect hybrid to match/beat isochrone
  - Long route (200nm) complex weather → Expect isochrone to win
  - Upwind, downwind, and beam reach scenarios
  - Verify routes respect no-go zones and use proper sailing tactics

**Goal**: Replace naive geometric routes with wind-optimized routes using BOTH pattern-based heuristics and optimal isochrone search. User always gets the 3 best routes automatically.

### Phase 6: Polish & Testing (Days 14-15)
Make it interview-ready.

- [ ] Test with various routes (short, long, different regions)
- [ ] Handle edge cases
- [ ] Improve error messages
- [ ] Add loading animations
- [ ] Make responsive for mobile
- [ ] Performance optimization

### Phase 7: Documentation & Demo Prep (Days 16-17)
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
│   ├── main.py             # Local testing entry point
│   └── lambda_function.py  # AWS Lambda handler
│
├── frontend/               # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/
│   │   │   ├── Map.tsx           # Leaflet map with markers & routes
│   │   │   ├── RouteForm.tsx     # Boat selector & controls
│   │   │   ├── RouteCards.tsx    # Route comparison cards
│   │   │   └── WeatherPanel.tsx  # Weather details panel
│   │   ├── services/
│   │   │   └── api.ts            # Lambda API connection
│   │   ├── types/
│   │   │   └── index.ts          # TypeScript type definitions
│   │   ├── App.tsx               # Main app component
│   │   ├── main.tsx              # Entry point
│   │   └── index.css             # Tailwind imports
│   ├── vite.config.ts            # Vite + proxy config
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

- [x] User can select start/end points on a map
- [x] System generates 3 distinct route recommendations
- [x] Each route shows real weather conditions
- [x] Routes are scored and ranked
- [x] Beautiful, professional UI
- [x] Fully deployed and accessible via URL (Phase 4)
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
| Phase 1: Backend Algorithm (Naive) | ✅ Done | Python code working locally |
| Phase 2: Lambda Deployment | ✅ Done | API live at AWS! |
| Phase 3: Frontend Development | ✅ Done | React app with beautiful UI |
| Phase 4: Frontend Deployment | ✅ Done | Live at CloudFront! |
| Phase 5: Smart Route Algorithm | ⬜ Not started | Next step - Wind-aware routing |
| Phase 6: Polish & Testing | ⬜ Not started | |
| Phase 7: Documentation | ⬜ Not started | |

---

**Timeline:** ~17 days (prioritizing smart algorithm over polish)
**Current Status:** Phase 4 COMPLETE! App is live at https://d2zb6habqv1546.cloudfront.net
**Next Priority:** Phase 5 - Smart Route Algorithm (wind-aware routing)
