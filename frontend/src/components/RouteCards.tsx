import type { Route } from '../types';

interface RouteCardsProps {
  routes: Route[];
  selectedIndex: number | null;
  onSelectRoute: (index: number) => void;
}

// Helper function to convert UTC ISO string to local time format
function formatLocalTime(isoString: string): string {
  const date = new Date(isoString);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

// Utility function to convert routes to CSV
function routesToCSV(routes: Route[]): string {
  // CSV headers
  const headers = [
    'Route Name',
    'Waypoint Number',
    'Latitude',
    'Longitude',
    'Estimated Arrival',
    'Wind Speed (knots)',
    'Wind Sustained (knots)',
    'Wind Gusts (knots)',
    'Wind Direction (degrees)',
    'Wave Height (meters)',
    'Temperature (celsius)',
    'Precipitation (mm)',
    'Visibility (km)'
  ];

  // Build CSV rows
  const rows: string[] = [headers.join(',')];

  routes.forEach((route) => {
    route.waypoints.forEach((waypoint, index) => {
      // Convert UTC ISO string to local time for CSV export
      const localTime = formatLocalTime(waypoint.estimatedArrival);
      const row = [
        `"${route.name}"`,
        (index + 1).toString(),
        waypoint.position.lat.toString(),
        waypoint.position.lng.toString(),
        `"${localTime}"`,
        waypoint.weather?.windSpeed.toString() ?? '',
        waypoint.weather?.windSustained.toString() ?? '',
        waypoint.weather?.windGusts.toString() ?? '',
        waypoint.weather?.windDirection.toString() ?? '',
        waypoint.weather?.waveHeight.toString() ?? '',
        waypoint.weather?.temperature.toString() ?? '',
        waypoint.weather?.precipitation.toString() ?? '',
        waypoint.weather?.visibility.toString() ?? ''
      ];
      rows.push(row.join(','));
    });
  });

  return rows.join('\n');
}

// Utility function to download CSV
function downloadCSV(csvContent: string, filename: string) {
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  URL.revokeObjectURL(url);
}

function RouteCard({ 
  route, 
  onWaypointClick
}: { 
  route: Route; 
  onWaypointClick?: (waypointIndex: number) => void;
}) {
  const windCompass = (degrees: number): string => {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const index = Math.round(degrees / 45) % 8;
    return directions[index];
  };

  return (
    <div className="relative p-6 rounded-xl bg-slate-800/60 border-2 border-slate-700 shadow-lg">
      {/* Header */}
      <div className="mb-4">
        <h3 className="font-bold text-xl text-blue-400 flex items-center gap-2">
          <span>📍</span>
          Waypoints & Weather Details
        </h3>
        <p className="text-slate-400 text-sm mt-1">Estimated Time: {route.estimatedTime}</p>
      </div>

      {/* Regular Warnings */}
      {route.warnings.length > 0 && (
        <div className="mb-4 space-y-1">
          {route.warnings.map((warning, i) => (
            <div key={i} className="flex items-start gap-2 text-amber-400 text-xs bg-amber-500/10 rounded p-2">
              <span className="shrink-0">⚠️</span>
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      {/* Waypoints with Weather */}
      <div>
        <div className="space-y-3 max-h-[calc(100vh-300px)] overflow-y-auto pr-2">
          {route.waypoints.map((waypoint, idx) => (
            <div 
              key={idx} 
              onClick={() => onWaypointClick?.(idx)}
              className="bg-slate-900/50 rounded-lg p-3 border border-slate-700 cursor-pointer hover:border-blue-500 transition-colors"
            >
              {/* Waypoint Header */}
              <div className="flex justify-between items-start mb-2">
                <div>
                  <p className="text-blue-400 font-semibold text-sm">
                    Waypoint {idx + 1}
                    {idx === 0 && <span className="text-green-400 ml-2">🚩 Start</span>}
                    {idx === route.waypoints.length - 1 && <span className="text-red-400 ml-2">🏁 End</span>}
                  </p>
                  <p className="text-white text-sm font-semibold mt-1">
                    {waypoint.position.lat.toFixed(4)}°, {waypoint.position.lng.toFixed(4)}°
                  </p>
                </div>
                <p className="text-slate-400 text-xs">
                  {formatLocalTime(waypoint.estimatedArrival)}
                </p>
              </div>

              {/* Weather Data */}
              {waypoint.weather && (
                <div className="space-y-2 mt-2">
                  {/* Primary Weather Info - Highlighted */}
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-slate-800/50 rounded p-2 flex items-center gap-2">
                      <span>💨</span>
                      <div>
                        <p className="text-slate-500 text-xs">Wind</p>
                        <p className="text-white text-sm font-semibold">
                          {waypoint.weather.windSpeed.toFixed(0)} kt {windCompass(waypoint.weather.windDirection)}
                        </p>
                      </div>
                    </div>
                    <div className="bg-slate-800/50 rounded p-2 flex items-center gap-2">
                      <span>🌊</span>
                      <div>
                        <p className="text-slate-500 text-xs">Waves</p>
                        <p className="text-white text-sm font-semibold">
                          {waypoint.weather.waveHeight.toFixed(1)} m
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {/* Secondary Weather Info */}
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div className="bg-slate-800/30 rounded p-1.5 text-center">
                      <p className="text-slate-500">Gusts</p>
                      <p className="text-white font-semibold">
                        {waypoint.weather.windGusts.toFixed(0)} kt
                      </p>
                    </div>
                    <div className="bg-slate-800/30 rounded p-1.5 text-center">
                      <p className="text-slate-500">🌡️ Temp</p>
                      <p className="text-white font-semibold">
                        {waypoint.weather.temperature.toFixed(0)}°C
                      </p>
                    </div>
                    <div className="bg-slate-800/30 rounded p-1.5 text-center">
                      <p className="text-slate-500">👁️ Vis</p>
                      <p className="text-white font-semibold">
                        {waypoint.weather.visibility.toFixed(0)} km
                      </p>
                    </div>
                  </div>

                  {/* Precipitation if present */}
                  {waypoint.weather.precipitation > 0 && (
                    <div className="flex items-center gap-2 text-xs text-sky-400 bg-sky-500/10 rounded p-2">
                      <span>🌧️</span>
                      <span>{waypoint.weather.precipitation.toFixed(1)} mm rain</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface RouteCardsPropsWithCallbacks extends RouteCardsProps {
  onWaypointClick?: (waypointIndex: number) => void;
}

export default function RouteCards({ routes, selectedIndex, onWaypointClick }: RouteCardsPropsWithCallbacks) {
  if (routes.length === 0) {
    return (
      <div className="bg-slate-800/60 rounded-xl p-6 text-center border border-slate-700">
        <p className="text-slate-400 text-lg mb-2">🗺️</p>
        <p className="text-slate-400">No routes calculated yet</p>
        <p className="text-slate-500 text-sm mt-1">
          Set start and end points, then click Calculate
        </p>
      </div>
    );
  }

  // Get the selected route, or default to the first route if none selected
  const selectedRoute = selectedIndex !== null ? routes[selectedIndex] : routes[0];

  // Handle CSV download for the selected route only
  const handleDownloadCSV = () => {
    const csvContent = routesToCSV([selectedRoute]);
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    const filename = `route-waypoints-${timestamp}.csv`;
    downloadCSV(csvContent, filename);
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <span>🗺️</span>
          Route Details
        </h3>
        <button
          onClick={handleDownloadCSV}
          className="bg-gradient-to-r from-green-300 via-emerald-400 to-teal-400 hover:from-green-400 hover:via-emerald-500 hover:to-teal-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-all shadow-lg hover:shadow-xl"
          title="Download waypoints as CSV"
        >
          <span>⬇️</span>
          <span>Download CSV</span>
        </button>
      </div>
      
      <RouteCard
        route={selectedRoute}
        onWaypointClick={onWaypointClick}
      />
    </div>
  );
}

