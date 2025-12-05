import type { Route, Waypoint } from '../types';

interface WeatherPanelProps {
  route: Route | null;
}

function WeatherIcon({ condition }: { condition: string }) {
  const icons: Record<string, string> = {
    wind: '💨',
    wave: '🌊',
    temp: '🌡️',
    rain: '🌧️',
    visibility: '👁️',
  };
  return <span>{icons[condition] || '📊'}</span>;
}

function WaypointWeather({ waypoint, index }: { waypoint: Waypoint; index: number }) {
  const weather = waypoint.weather;
  
  if (!weather) {
    return (
      <div className="bg-slate-900/50 rounded-lg p-3">
        <p className="text-slate-500 text-sm">No weather data</p>
      </div>
    );
  }

  // Wind direction to compass
  const windCompass = (degrees: number): string => {
    const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const index = Math.round(degrees / 45) % 8;
    return directions[index];
  };

  // Color coding for values
  const getWindColor = (speed: number) => {
    if (speed > 35) return 'text-red-400';
    if (speed > 25) return 'text-orange-400';
    if (speed > 15) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  const getWaveColor = (height: number) => {
    if (height > 3) return 'text-red-400';
    if (height > 2) return 'text-orange-400';
    if (height > 1) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  return (
    <div className="bg-slate-900/50 rounded-lg p-3">
      <div className="flex justify-between items-center mb-2">
        <span className="text-slate-400 text-xs">Point {index + 1}</span>
        <span className="text-slate-500 text-xs font-mono">
          {waypoint.position.lat.toFixed(2)}, {waypoint.position.lng.toFixed(2)}
        </span>
      </div>
      
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="flex items-center gap-2">
          <WeatherIcon condition="wind" />
          <span className={getWindColor(weather.windSpeed)}>
            {weather.windSpeed.toFixed(0)}kt {windCompass(weather.windDirection)}
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <WeatherIcon condition="wave" />
          <span className={getWaveColor(weather.waveHeight)}>
            {weather.waveHeight.toFixed(1)}m
          </span>
        </div>
        
        <div className="flex items-center gap-2">
          <WeatherIcon condition="temp" />
          <span className="text-slate-300">{weather.temperature.toFixed(0)}°C</span>
        </div>
        
        <div className="flex items-center gap-2">
          <WeatherIcon condition="visibility" />
          <span className={weather.visibility < 5 ? 'text-orange-400' : 'text-slate-300'}>
            {weather.visibility.toFixed(0)}km
          </span>
        </div>
      </div>
      
      {weather.precipitation > 0 && (
        <div className="flex items-center gap-2 mt-2 text-sm text-sky-400">
          <WeatherIcon condition="rain" />
          <span>{weather.precipitation.toFixed(1)}mm rain</span>
        </div>
      )}
    </div>
  );
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
        <span>🌤️</span>
        Weather Along Route
      </h3>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Avg Wind</p>
          <p className="text-white font-bold">{avgWind.toFixed(0)} kt</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Max Wind</p>
          <p className={`font-bold ${maxWind > 30 ? 'text-red-400' : 'text-white'}`}>
            {maxWind.toFixed(0)} kt
          </p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Avg Waves</p>
          <p className="text-white font-bold">{avgWave.toFixed(1)} m</p>
        </div>
        <div className="bg-slate-900/70 rounded-lg p-2 text-center">
          <p className="text-slate-500 text-xs">Max Waves</p>
          <p className={`font-bold ${maxWave > 2.5 ? 'text-orange-400' : 'text-white'}`}>
            {maxWave.toFixed(1)} m
          </p>
        </div>
      </div>

      {/* Waypoint details */}
      <div className="space-y-2 max-h-64 overflow-y-auto">
        {route.waypoints.map((waypoint, index) => (
          <WaypointWeather key={index} waypoint={waypoint} index={index} />
        ))}
      </div>
    </div>
  );
}

