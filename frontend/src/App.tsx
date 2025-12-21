import { useState } from 'react';
import Map from './components/Map';
import RouteForm from './components/RouteForm';
import RouteCards from './components/RouteCards';
import WeatherPanel from './components/WeatherPanel';
import { calculateRoutes } from './services/api';
import type { Coordinates, Route, BoatType, WeatherGrid } from './types';

function App() {
  // State for user inputs
  const [startPoint, setStartPoint] = useState<Coordinates | null>(null);
  const [endPoint, setEndPoint] = useState<Coordinates | null>(null);
  const [boatType, setBoatType] = useState<BoatType>('sailboat');
  // Default to current time in ISO format (YYYY-MM-DDTHH:mm)
  const [departureTime, setDepartureTime] = useState<string>(() => {
    const now = new Date();
    // Format as YYYY-MM-DDTHH:mm for datetime-local input
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${year}-${month}-${day}T${hours}:${minutes}`;
  });

  // State for API response
  const [routes, setRoutes] = useState<Route[]>([]);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState<number | null>(null);
  const [weatherGrid, setWeatherGrid] = useState<WeatherGrid | null>(null);
  
  // State for loading/error
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // State for no-go zone highlighting
  const [highlightedNoGoZone, setHighlightedNoGoZone] = useState<number | null>(null);
  
  // State for waypoint highlighting
  const [highlightedWaypoint, setHighlightedWaypoint] = useState<number | null>(null);

  // Handle route calculation
  const handleCalculate = async () => {
    if (!startPoint || !endPoint) return;

    setLoading(true);
    setError(null);
    setRoutes([]);
    setSelectedRouteIndex(null);

    try {
      // Convert datetime-local format to ISO string for API
      const departureTimeISO = new Date(departureTime).toISOString();
      
      const response = await calculateRoutes({
        start: startPoint,
        end: endPoint,
        boat_type: boatType,
        departure_time: departureTimeISO,
      });
      
      console.log('Routes received:', response.routes);
      response.routes.forEach((route: Route, idx: number) => {
        console.log(`Route ${idx}:`, route.name, 'violations:', route.noGoZoneViolations);
      });
      setRoutes(response.routes);
      setWeatherGrid(response.weatherGrid || null);
      // Auto-select the best route (first one after sorting by score)
      if (response.routes.length > 0) {
        const bestRouteIndex = response.routes.reduce(
          (best, route, index) => route.score > response.routes[best].score ? index : best,
          0
        );
        setSelectedRouteIndex(bestRouteIndex);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to calculate routes');
    } finally {
      setLoading(false);
    }
  };

  // Clear all points and routes
  const handleClear = () => {
    setStartPoint(null);
    setEndPoint(null);
    setRoutes([]);
    setSelectedRouteIndex(null);
    setError(null);
    setWeatherGrid(null);
  };

  // Get selected route for weather panel
  const selectedRoute = selectedRouteIndex !== null ? routes[selectedRouteIndex] : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Header */}
      <header className="bg-slate-900/80 backdrop-blur-sm border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-3xl">⛵</span>
            <div>
              <h1 className="text-2xl font-bold text-white">Smart Sailing Planner</h1>
              <p className="text-slate-400 text-sm">Weather-optimized route recommendations</p>
            </div>
          </div>
          <div className="text-slate-500 text-sm">
            Powered by Open-Meteo Weather API
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left sidebar - Form and Weather */}
          <div className="lg:col-span-1 space-y-6">
            <RouteForm
              startPoint={startPoint}
              endPoint={endPoint}
              boatType={boatType}
              departureTime={departureTime}
              loading={loading}
              hasRoutes={routes.length > 0}
              onBoatTypeChange={setBoatType}
              onDepartureTimeChange={setDepartureTime}
              onCalculate={handleCalculate}
              onClear={handleClear}
            />

            {/* Error display */}
            {error && (
              <div className="bg-red-500/10 border border-red-500 rounded-xl p-4">
                <p className="text-red-400 text-sm flex items-center gap-2">
                  <span>❌</span>
                  {error}
                </p>
              </div>
            )}

            {/* Weather panel - show when route selected */}
            {selectedRoute && (
              <WeatherPanel route={selectedRoute} />
            )}
          </div>

          {/* Right side - Map on top, Route Cards below */}
          <div className="lg:col-span-2 space-y-6">
            {/* Map */}
            <div className="h-[400px] lg:h-[450px]">
              <Map
                startPoint={startPoint}
                endPoint={endPoint}
                routes={routes}
                selectedRouteIndex={selectedRouteIndex}
                onStartPointChange={setStartPoint}
                onEndPointChange={setEndPoint}
                highlightedNoGoZone={highlightedNoGoZone}
                highlightedWaypoint={highlightedWaypoint}
                weatherGrid={weatherGrid}
              />
            </div>

            {/* Route Cards - below the map */}
            <RouteCards
              routes={routes}
              selectedIndex={selectedRouteIndex}
              onSelectRoute={setSelectedRouteIndex}
              onNoGoZoneClick={(routeIndex, segmentIndex) => {
                setSelectedRouteIndex(routeIndex);
                setHighlightedNoGoZone(segmentIndex);
                setHighlightedWaypoint(null);
              }}
              onWaypointClick={(waypointIndex) => {
                setHighlightedWaypoint(waypointIndex);
                setHighlightedNoGoZone(null);
              }}
            />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-slate-900/50 border-t border-slate-800 px-6 py-4 mt-8">
        <div className="max-w-7xl mx-auto text-center text-slate-500 text-sm">
          <p>🌊 Built for sailors who love data-driven decisions</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
