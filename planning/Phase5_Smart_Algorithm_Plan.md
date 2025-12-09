# Phase 5: Smart Sailing Route Algorithm - Detailed Plan

## Executive Summary

**Current State**: System uses naive geometric routes (straight line, curve left, curve right) that ignore wind conditions during generation.

**Goal**: Implement TWO wind-aware routing algorithms:
1. **Hybrid Pattern-Based** - Fast heuristic approach using proven sailing tactics
2. **Isochrone Optimization** - Optimal search method (industry standard)

**Strategy**: Run both algorithms, score all routes, return top 3. This ensures optimal routes while maintaining fast performance on simple scenarios.

**Timeline**: 10 days (Days 11-20 of overall project)

---

## Background: Why Sailing Routing is Unique

### The Challenge

Sailing route optimization differs fundamentally from road routing:

1. **No-Go Zones**: Boats cannot sail directly into wind (±45° dead zone)
2. **Variable Speed**: Boat speed depends on both wind speed AND wind angle
3. **Non-Linear Paths**: Optimal route often involves sailing at angles away from destination
4. **Time-Varying Conditions**: Weather changes as boat travels

### Example Scenario

**Route**: Southampton to Cherbourg (80 nautical miles south)  
**Wind**: 15 knots from the south (destination direction)

**Naive Approach** (current):
- Generate straight line south → Score: 20/100 (can't sail directly into wind!)

**Smart Approach** (Phase 5):
- **Hybrid**: Generate tacking route (zigzag at 52° angles) → Score: 85/100
- **Isochrone**: Find optimal tacking pattern with wind shifts → Score: 90/100
- **Return**: Top 3 routes (likely 2 from isochrone, 1 from hybrid)

---

## Algorithm Comparison

### When Each Algorithm Excels

| Scenario | Hybrid Performance | Isochrone Performance | Winner |
|----------|-------------------|----------------------|--------|
| Short route (<100nm), uniform wind | ⭐⭐⭐⭐⭐ Fast & optimal | ⭐⭐⭐⭐ Slower, same result | Hybrid |
| Long route (>200nm), complex weather | ⭐⭐⭐ Good patterns | ⭐⭐⭐⭐⭐ Finds optimal path | Isochrone |
| Upwind sailing, steady conditions | ⭐⭐⭐⭐ Tacking patterns work well | ⭐⭐⭐⭐⭐ Perfect tacking angles | Tie/Isochrone |
| Weather front passing through route | ⭐⭐ Misses opportunities | ⭐⭐⭐⭐⭐ Routes around front | Isochrone |

### Algorithm 1: Hybrid Pattern-Based

**Philosophy**: "Use established sailing tactics and patterns"

**How It Works**:
```
1. Fetch weather for route area
2. Analyze: Is destination upwind, downwind, or beam reach?
3. Apply sailing tactics:
   - Upwind → Generate tacking routes (zigzag at optimal VMG angles)
   - Downwind → Generate broad reach routes (slightly off course for speed)
   - Beam reach → Generate direct or wind-seeking routes
4. Return 3 route variations
```

**Strengths**:
- ✅ Very fast (< 1 second)
- ✅ Uses real sailing knowledge (not a black box)
- ✅ Excellent for simple scenarios
- ✅ Easy to explain and debug

**Weaknesses**:
- ❌ Pre-defined patterns (can miss creative solutions)
- ❌ Assumes uniform conditions along route
- ❌ May not handle complex weather optimally

**Computation Time**: ~0.5 seconds

### Algorithm 2: Isochrone Method

**Philosophy**: "Explore all possibilities, find mathematically optimal path"

**How It Works**:
```
1. Start at origin at t=0
2. For each time step (e.g., 1 hour):
   a. From current reachable points, try all headings (0°, 10°, 20°, ..., 350°)
   b. Calculate boat speed using polars + wind at each point
   c. Compute new reachable positions
   d. Prune dominated solutions
3. Continue until destination reached
4. Trace back optimal path(s)
5. Generate 2-3 variations (fastest, safest, moderate)
```

**Strengths**:
- ✅ Industry standard (used by professional navigators)
- ✅ Finds globally optimal solution
- ✅ Handles time-varying weather naturally
- ✅ Discovers non-obvious optimal routes

**Weaknesses**:
- ❌ More complex to implement
- ❌ Slower computation (3-5 seconds)
- ❌ Requires tuning (time step, angular resolution)

**Computation Time**: ~3-5 seconds

**References**:
- Used by: OpenCPN Weather Routing Plugin, qtVlm, expedition marine
- Algorithm: https://en.wikipedia.org/wiki/Isochrone_map
- Implementation reference: https://github.com/OpenCPN/weather_routing_pi

---

## Core Sailing Concepts

### 1. Polar Diagrams

A polar diagram is a lookup table that defines boat performance:

**Input**: Wind speed (TWS) + Wind angle (TWA)  
**Output**: Boat speed (knots)

**Example Polar Data** (Typical 40ft sailboat):

```python
SAILBOAT_POLAR = {
    6: {   # 6 knots true wind speed
        0: 0.0,     # Dead upwind - impossible
        30: 0.0,    # Too close to wind
        45: 0.0,    # Still in no-go zone
        52: 3.2,    # Close-hauled (optimal upwind angle)
        60: 3.8,    # Close-hauled
        75: 4.1,    # Close reach
        90: 4.3,    # Beam reach
        110: 4.7,   # Broad reach (FASTEST for this wind speed)
        135: 4.5,   # Broad reach
        150: 4.0,   # Running
        180: 3.5,   # Dead downwind (slower than angled)
    },
    10: {  # 10 knots wind
        52: 5.5,    # Faster in more wind
        90: 7.2,
        110: 7.8,   # Still fastest angle
        # ... etc
    },
    # ... more wind speeds (15, 20, 25, 30 knots)
}
```

**Key Insight**: Dead downwind (180°) is often SLOWER than sailing at an angle (110-135°)!

**Where to Get Polars**:
- **Simplified**: Use theoretical polars (good enough for MVP)
- **Real Data**: https://jieter.github.io/orc-data/ (open source racing polars)
- **Official**: https://orc.org/ (Offshore Racing Congress database)

### 2. VMG (Velocity Made Good)

**Definition**: Component of boat speed in direction of destination

**Formula**: `VMG = boat_speed × cos(angle_off_course)`

**Example**:
```
Destination: Due North (0°)
Wind: From North (can't sail directly)

Option A: Try to sail north at 350° (10° off wind)
→ Boat speed: 1.5 knots (very slow, too close to wind)
→ VMG: 1.5 × cos(10°) = 1.48 knots toward destination

Option B: Tack at 52° off wind (heading 52°)
→ Boat speed: 6.0 knots (good speed)
→ VMG: 6.0 × cos(52°) = 3.69 knots toward destination

Option B is 2.5× faster toward destination!
```

**Optimal VMG Angle**: The heading that maximizes VMG (usually 50-52° for upwind, varies for other conditions)

### 3. No-Go Zone

Sailboats cannot sail closer than ~45° to the wind direction.

**Example**:
```
Wind from North (0°):
  - Cannot sail: 315° to 045° (90° total no-go zone)
  - Can sail: 045° to 315° (all other directions)

If destination is at 010° (upwind):
  - Must tack (zigzag) at 52° and 308° alternately
  - Never point directly at destination until very close
```

### 4. True Wind vs Apparent Wind

**True Wind**: Wind relative to the water (what weather forecasts provide)  
**Apparent Wind**: Wind felt by the moving boat

**For Route Planning**: We use **true wind** from forecasts and calculate boat performance based on boat heading relative to true wind direction.

### 5. Tacking (Upwind Sailing)

When destination is upwind, must zigzag:

```
       Destination (N)
            ↑
           /|\
          / | \
    52° /  |  \ 308°
       /   |   \
      /    |    \
     /     |     \
   Tack 1  |  Tack 2
          Start

Wind from North (↓)
```

**Optimal Tacking Strategy**:
- Tack angle: 50-52° off wind (from polar diagram)
- Number of tacks: Depends on distance and wind shifts
- Minimize tacks (each tack loses time)

---

## Implementation Details

### Phase 5A: Foundation & Hybrid (Days 11-14)

#### Task 1: Polar Diagrams Module

**File**: `backend/polars.py` (new)

**What to Implement**:
- Define polar data tables for each boat type (sailboat, motorboat, catamaran)
- Polar structure: nested dictionary `{boat_type: {wind_speed: {wind_angle: boat_speed}}}`
- Include wind speeds: 6, 10, 15, 20, 25, 30, 35 knots
- Include wind angles: 0°, 45°, 52°, 60°, 75°, 90°, 110°, 135°, 150°, 180°

**Key Functions**:
- `get_boat_speed(wind_speed, wind_angle, boat_type)` - Use bilinear interpolation
- `get_optimal_vmg_angle(wind_speed, boat_type, destination_bearing, wind_direction)` - Find heading that maximizes VMG
- Handle no-go zone (angles < 45° return 0 speed)
- Normalize wind angles to 0-180° (polars are symmetric)

**Testing**:
- Unit test: `get_boat_speed(10, 90, SAILBOAT)` should return ~7.2 knots
- Unit test: `get_boat_speed(10, 30, SAILBOAT)` should return 0 (no-go zone)
- Unit test: Interpolation between wind speeds (e.g., 12 knots wind)

#### Task 2: Regional Weather Grid

**File**: `backend/weather_fetcher.py` (modify existing)

**What to Add**:

**Function**: `fetch_regional_weather_grid(start, end, departure_time, grid_spacing=10.0)`
- Calculate bounding box covering route area with 0.5° padding on all sides
- Generate grid of points spaced ~10 nautical miles apart
- Use Open-Meteo's batched API call (supports multiple lat/lng in single request)
- Return dictionary indexed by (lat, lng, time)

**Function**: `interpolate_weather(position, time, weather_grid)`
- Find 4 nearest grid points surrounding the target position
- Perform bilinear interpolation in space
- Perform linear interpolation in time
- Return interpolated WaypointWeather object

#### Task 3: Wind Analysis & Scenario Classification

**File**: `backend/wind_router.py` (new)

**What to Implement**:

**Enum**: `SailingScenario`
- UPWIND (angle < 60°) - Destination is upwind, must tack
- BEAM_REACH (60° ≤ angle < 100°) - Wind from side, fast sailing
- BROAD_REACH (100° ≤ angle < 150°) - Wind from behind-side
- DOWNWIND (angle ≥ 150°) - Destination is downwind

**Function**: `classify_sailing_scenario(start, end, wind_direction)`
- Calculate bearing from start to destination
- Calculate angle between destination bearing and wind direction
- Handle 0°/360° wraparound
- Return appropriate scenario classification

**Function**: `analyze_wind_corridor(start, end, weather_grid)`
- Sample wind at multiple points along direct route
- Calculate statistics: avg wind speed, avg wind direction, max wind speed, wind variability
- Return dictionary with analysis results

#### Task 4: Hybrid Route Generator

**File**: `backend/wind_router.py` (continued)

**Main Function**: `generate_hybrid_routes(request)`
- Fetch regional weather grid
- Analyze wind corridor
- Classify sailing scenario
- Dispatch to appropriate route generator based on scenario

**Function**: `generate_upwind_routes(request, weather_grid, wind_analysis)`
- Generate 3 tacking route variations:
  - **Conservative**: 2 long tacks at 52° angle
  - **Aggressive**: 4 shorter tacks at 50° angle
  - **Wind-seeking**: Favor side with stronger wind
- Return list of GeneratedRoute objects

**Function**: `generate_downwind_routes(request, weather_grid, wind_analysis)`
- Generate 3 downwind variations:
  - **Direct**: Straight or nearly straight route
  - **Port broad reach**: Curve right ~30° for better boat speed
  - **Starboard broad reach**: Curve left ~30° for better boat speed

**Function**: `generate_reaching_routes(request, weather_grid, wind_analysis)`
- Generate 3 reaching (beam/broad reach) variations:
  - **Direct**: Straight path (already good wind angle)
  - **Wind-seeking**: Curve toward areas with stronger wind
  - **Smooth**: Avoid areas with high waves or dangerous conditions

**Helper Function**: `generate_tacking_route(start, end, wind_direction, num_tacks, tack_angle, boat_type)`
- Create zigzag waypoints alternating between port and starboard tacks
- Distribute distance evenly across tacks
- Calculate arrival times at each waypoint

### Phase 5B: Isochrone Algorithm (Days 15-19)

#### Task 5: Isochrone Core

**File**: `backend/isochrone_router.py` (new)

**Data Structure**: `IsochronePoint` (dataclass)
- Fields: position (Coordinates), time (float), cost (float), parent (IsochronePoint)
- Represents a point reachable at a specific time with accumulated cost
- Parent pointer enables path reconstruction

**Main Function**: `generate_isochrone_routes(request)`
- Fetch regional weather grid
- Run isochrone search to find optimal paths
- Reconstruct top 3 solution paths
- Convert to GeneratedRoute objects and return

**Core Algorithm**: `isochrone_search(start, end, weather_grid, boat_type, departure_time, ...)`
- **Parameters**: time_step=1.0 hours, angular_resolution=10°, max_time=240 hours
- **Algorithm**:
  1. Initialize with start point at t=0
  2. Loop while isochrone exists and solutions < 10:
     - Propagate forward by one time step
     - Check if any points reached destination (within 5nm)
     - Prune dominated solutions
  3. Sort solutions by cost, return best ones

**Function**: `propagate_isochrone(current_isochrone, time_step, angular_resolution, weather_grid, boat_type, departure_time)`
- For each point in current isochrone:
  - Try all headings (0°, 10°, 20°, ..., 350°)
  - Get weather at that position/time via interpolation
  - Calculate wind angle relative to heading
  - Get boat speed from polars
  - If boat speed > 0 (not in no-go zone):
    - Calculate new position after time_step hours
    - Create new IsochronePoint with parent pointer
- Return list of all reachable points at next time step

#### Task 6: Pruning & Path Reconstruction

**File**: `backend/isochrone_router.py` (continued)

**Function**: `prune_isochrone(isochrone, visited_grid, grid_size=0.1)`
- **Purpose**: Prevent exponential explosion of points while maintaining optimality
- **Strategy**:
  1. Divide space into grid cells (0.1° = ~6 nautical miles)
  2. Group points by cell (lat, lng, time bucket)
  3. In each cell, keep only the point with lowest cost
  4. Track visited cells to avoid revisiting with worse costs
- **Result**: Reduces O(n²) growth to manageable size

**Function**: `reconstruct_path(end_point)`
- Trace back from destination to start following parent pointers
- Build path list by iterating through parent chain
- Reverse list to get chronological order (start → end)
- Convert IsochronePoint objects to Waypoint objects
- Calculate actual arrival times for each waypoint
- Return list of Waypoints

### Phase 5C: Integration (Day 20)

#### Task 7: Combine Both Algorithms

**File**: `backend/lambda_function.py` (modify)

**Function**: `calculate_routes(request)` - Updated to run both algorithms

**Implementation Steps**:
1. **Run Hybrid Algorithm**:
   - Time the execution
   - Log: "Running hybrid pattern-based algorithm..."
   - Call `generate_hybrid_routes(request)`
   - Expected: 3 routes in ~0.5-1 second

2. **Run Isochrone Algorithm**:
   - Time the execution
   - Log: "Running isochrone optimization algorithm..."
   - Call `generate_isochrone_routes(request)`
   - Expected: 2-3 routes in ~3-5 seconds

3. **Fetch Weather**:
   - Combine all routes (5-6 total)
   - Call `fetch_weather_for_waypoints()` for each route
   - Attach weather data to waypoints

4. **Score All Routes**:
   - Calculate direct distance for normalization
   - Score each route using existing `score_route()` function
   - Results: 5-6 scored routes

5. **Select Top 3**:
   - Sort by score (descending)
   - Take top 3 routes
   - Log selected scores
   - Return RouteResponse with best 3 routes

**Key Point**: User always gets top 3 routes regardless of which algorithm generated them

#### Task 8: Testing & Validation

**Test Cases**:

1. **Short Uniform Route** (Hybrid should win)
   - Route: 50 nautical miles
   - Wind: Steady 15 knots from one direction
   - Expected: Hybrid and isochrone produce similar routes

2. **Long Complex Route** (Isochrone should win)
   - Route: 200+ nautical miles
   - Wind: Shifts 90° along route
   - Expected: Isochrone finds better path

3. **Upwind Scenario** (Both should tack)
   - Destination directly upwind
   - Expected: Both generate zigzag routes, isochrone optimizes tack points

4. **Downwind Scenario** (Test broad reach optimization)
   - Destination downwind
   - Expected: Both may suggest sailing at angle (110°) instead of dead downwind (180°)

---

## Performance Targets

| Metric | Hybrid Target | Isochrone Target | Combined |
|--------|--------------|------------------|----------|
| Computation Time | < 1 second | < 5 seconds | < 6 seconds |
| Route Quality | 85-95/100 | 90-100/100 | Best of both |
| Memory Usage | < 10 MB | < 50 MB | < 60 MB |
| Success Rate | > 99% | > 95% | > 99% |

---

## Success Criteria

✅ **Routes respect sailing physics**:
- Never sail in no-go zone (< 45° to wind)
- Use optimal tacking angles upwind (50-52°)
- Consider boat speed vs wind angle relationship

✅ **Better than naive baseline**:
- Smart routes score ≥10 points higher than geometric routes
- Realistic sailing patterns (not impossible maneuvers)

✅ **Performance**:
- Total computation < 10 seconds (hybrid + isochrone)
- Lambda function completes within timeout (30s)

✅ **Robustness**:
- Handles edge cases (very short routes, very long routes)
- Graceful degradation if one algorithm fails
- Works across different weather conditions

---

## Resources & References

### Sailing Theory
- **VMG Optimization**: Standard sailing navigation technique
- **Polar Diagrams**: https://orc.org/ (racing polars)
- **Open Source Polars**: https://jieter.github.io/orc-data/

### Isochrone Algorithm
- **Wikipedia**: https://en.wikipedia.org/wiki/Isochrone_map
- **OpenCPN Implementation**: https://github.com/OpenCPN/weather_routing_pi
  - Production C++ code, excellent reference
  - File: `src/WeatherRouting.cpp` has main algorithm
- **qtVlm**: Another open-source implementation

### Weather Data
- **Open-Meteo API**: https://open-meteo.com/
  - Marine API for wave data
  - Weather API for wind
  - Supports batched requests (perfect for grids)

---

## Next Steps After Phase 5

### Phase 6: Polish & Testing
- Test with real sailors (usability feedback)
- Handle edge cases
- Improve error messages
- Mobile responsiveness

### Phase 7: Documentation
- Write comprehensive README with architecture
- Prepare demo routes for interviews
- Create diagrams explaining algorithms
- Practice presentation

### Future Enhancements (Post-Interview)
- Add current/tide data (significantly affects routes)
- Real-time route updates (re-calculate as conditions change)
- Multi-day routes with rest stops
- Route comparison with actual GPS tracks
- Machine learning for polar estimation

---

**Document Version**: 1.0  
**Last Updated**: Phase 5 Planning  
**Status**: Ready for Implementation

