// Weather Fetcher - Gets weather data from Open-Meteo API (free, no API key needed)

import { Coordinates, Waypoint, WaypointWeather } from './types';

// Open-Meteo Marine API endpoint
const MARINE_API_URL = 'https://marine-api.open-meteo.com/v1/marine';
const WEATHER_API_URL = 'https://api.open-meteo.com/v1/forecast';

interface OpenMeteoMarineResponse {
  hourly: {
    time: string[];
    wave_height?: number[];
    wind_wave_height?: number[];
    swell_wave_height?: number[];
  };
}

interface OpenMeteoWeatherResponse {
  hourly: {
    time: string[];
    temperature_2m: number[];
    precipitation: number[];
    visibility: number[];
    wind_speed_10m: number[];
    wind_direction_10m: number[];
  };
}

/**
 * Convert m/s to knots
 */
function msToKnots(ms: number): number {
  return ms * 1.944;
}

/**
 * Fetch weather data for a single coordinate and time
 */
async function fetchWeatherForPoint(
  position: Coordinates,
  dateTime: string
): Promise<WaypointWeather> {
  const date = new Date(dateTime);
  const dateStr = date.toISOString().split('T')[0];
  const hour = date.getHours();

  try {
    // Fetch both marine and weather data in parallel
    const [marineData, weatherData] = await Promise.all([
      fetchMarineData(position, dateStr),
      fetchWeatherData(position, dateStr),
    ]);

    // Find the closest hour in the data
    const hourIndex = Math.min(hour, 23);

    return {
      windSpeed: Math.round(msToKnots(weatherData.hourly.wind_speed_10m[hourIndex] || 10) * 10) / 10,
      windDirection: Math.round(weatherData.hourly.wind_direction_10m[hourIndex] || 180),
      waveHeight: Math.round((marineData.hourly.wave_height?.[hourIndex] || 1) * 10) / 10,
      precipitation: Math.round((weatherData.hourly.precipitation[hourIndex] || 0) * 10) / 10,
      visibility: Math.round((weatherData.hourly.visibility[hourIndex] || 10000) / 1000), // Convert m to km
      temperature: Math.round(weatherData.hourly.temperature_2m[hourIndex] || 20),
    };
  } catch (error) {
    // Return default/fallback weather if API fails
    console.warn(`Weather fetch failed for ${position.lat}, ${position.lng}:`, error);
    return getDefaultWeather();
  }
}

/**
 * Fetch marine data (waves) from Open-Meteo
 */
async function fetchMarineData(
  position: Coordinates,
  date: string
): Promise<OpenMeteoMarineResponse> {
  const url = `${MARINE_API_URL}?latitude=${position.lat}&longitude=${position.lng}&hourly=wave_height,wind_wave_height,swell_wave_height&start_date=${date}&end_date=${date}`;
  
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`Marine API error: ${response.status}`);
  }
  
  return response.json() as Promise<OpenMeteoMarineResponse>;
}

/**
 * Fetch weather data (wind, temp, etc.) from Open-Meteo
 */
async function fetchWeatherData(
  position: Coordinates,
  date: string
): Promise<OpenMeteoWeatherResponse> {
  const url = `${WEATHER_API_URL}?latitude=${position.lat}&longitude=${position.lng}&hourly=temperature_2m,precipitation,visibility,wind_speed_10m,wind_direction_10m&start_date=${date}&end_date=${date}`;
  
  const response = await fetch(url);
  
  if (!response.ok) {
    throw new Error(`Weather API error: ${response.status}`);
  }
  
  return response.json() as Promise<OpenMeteoWeatherResponse>;
}

/**
 * Default weather when API is unavailable
 */
function getDefaultWeather(): WaypointWeather {
  return {
    windSpeed: 12,
    windDirection: 180,
    waveHeight: 1.2,
    precipitation: 0,
    visibility: 15,
    temperature: 18,
  };
}

/**
 * Fetch weather for all waypoints in a route
 */
export async function fetchWeatherForWaypoints(
  waypoints: Waypoint[]
): Promise<Waypoint[]> {
  console.log(`  Fetching weather for ${waypoints.length} waypoints...`);
  
  // Fetch weather for all waypoints in parallel
  const weatherPromises = waypoints.map((wp) =>
    fetchWeatherForPoint(wp.position, wp.estimatedArrival)
  );
  
  const weatherResults = await Promise.all(weatherPromises);
  
  // Attach weather to waypoints
  return waypoints.map((wp, index) => ({
    ...wp,
    weather: weatherResults[index],
  }));
}

/**
 * Get a summary of weather conditions for display
 */
export function summarizeWeather(waypoints: Waypoint[]): {
  avgWindSpeed: number;
  maxWindSpeed: number;
  avgWaveHeight: number;
  maxWaveHeight: number;
  hasRain: boolean;
  avgVisibility: number;
} {
  const weathers = waypoints.map((wp) => wp.weather).filter(Boolean) as WaypointWeather[];
  
  if (weathers.length === 0) {
    return {
      avgWindSpeed: 0,
      maxWindSpeed: 0,
      avgWaveHeight: 0,
      maxWaveHeight: 0,
      hasRain: false,
      avgVisibility: 10,
    };
  }
  
  const windSpeeds = weathers.map((w) => w.windSpeed);
  const waveHeights = weathers.map((w) => w.waveHeight);
  const visibilities = weathers.map((w) => w.visibility);
  
  return {
    avgWindSpeed: Math.round(average(windSpeeds) * 10) / 10,
    maxWindSpeed: Math.round(Math.max(...windSpeeds) * 10) / 10,
    avgWaveHeight: Math.round(average(waveHeights) * 10) / 10,
    maxWaveHeight: Math.round(Math.max(...waveHeights) * 10) / 10,
    hasRain: weathers.some((w) => w.precipitation > 0.5),
    avgVisibility: Math.round(average(visibilities)),
  };
}

function average(nums: number[]): number {
  return nums.reduce((a, b) => a + b, 0) / nums.length;
}

