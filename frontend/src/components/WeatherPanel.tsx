import type { Route } from '../types';

interface WeatherPanelProps {
  route: Route | null;
}

export default function WeatherPanel({ route }: WeatherPanelProps) {
  if (!route) {
    return (
      <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700">
        <p className="text-slate-400 text-center">
          Select a route to see weather details
        </p>
      </div>
    );
  }

  // Calculate averages
  const validWeather = route.waypoints.filter(w => w.weather);
  const avgWind = validWeather.length > 0
    ? validWeather.reduce((sum, w) => sum + (w.weather?.windSpeed || 0), 0) / validWeather.length
    : 0;
  const avgWave = validWeather.length > 0
    ? validWeather.reduce((sum, w) => sum + (w.weather?.waveHeight || 0), 0) / validWeather.length
    : 0;
  const maxWind = Math.max(...validWeather.map(w => w.weather?.windSpeed || 0));
  const maxWave = Math.max(...validWeather.map(w => w.weather?.waveHeight || 0));

  return (
    <div className="bg-slate-800/60 rounded-xl p-4 border border-slate-700">
      <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
        <span>📊</span>
        Route Summary
      </h3>

      {/* Route Info */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Distance</p>
          <p className="text-white font-bold">{route.distance.toFixed(1)} km</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Waypoints</p>
          <p className="text-white font-bold">{route.waypoints.length}</p>
        </div>
      </div>

      {/* Weather Summary Header */}
      <div className="flex items-center gap-2 mb-2 mt-4">
        <span>🌤️</span>
        <h4 className="text-white font-semibold text-sm">Weather Summary</h4>
      </div>

      {/* Weather stats */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Avg Wind</p>
          <p className="text-white font-bold">{avgWind.toFixed(0)} kt</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Max Wind</p>
          <p className="text-white font-bold">{maxWind.toFixed(0)} kt</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Avg Waves</p>
          <p className="text-white font-bold">{avgWave.toFixed(1)} m</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Max Waves</p>
          <p className="text-white font-bold">{maxWave.toFixed(1)} m</p>
        </div>
      </div>
    </div>
  );
}

