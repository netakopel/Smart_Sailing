import { useState, useEffect, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Circle, CircleMarker, useMapEvents, Popup, useMap } from 'react-leaflet';
import { Icon, DivIcon, type LatLngExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Coordinates, Route, WeatherGrid } from '../types';
import { getUserLocation } from '../services/geolocation';

// Fix for default marker icons in Leaflet with bundlers
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

// Custom icons for start and end markers
const startIcon = new Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
  className: 'start-marker'
});

const endIcon = new Icon({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
  className: 'end-marker'
});

// Route colors - expanded palette for multiple routes
const ROUTE_COLOR_PALETTE = [
  '#3b82f6',  // Blue
  '#22c55e',  // Green
  '#f97316',  // Orange
  '#a855f7',  // Purple
  '#ec4899',  // Pink
  '#14b8a6',  // Teal
  '#f59e0b',  // Amber
  '#ef4444',  // Red
  '#06b6d4',  // Cyan
  '#8b5cf6',  // Violet
];

// Helper function to get color by index
const getRouteColor = (index: number): string => {
  return ROUTE_COLOR_PALETTE[index % ROUTE_COLOR_PALETTE.length];
};

interface MapProps {
  startPoint: Coordinates | null;
  endPoint: Coordinates | null;
  routes: Route[];
  selectedRouteIndex: number | null;
  onStartPointChange: (coords: Coordinates) => void;
  onEndPointChange: (coords: Coordinates) => void;
  highlightedNoGoZone?: number | null;  // Waypoint index to highlight
  highlightedWaypoint?: number | null;  // Waypoint index to highlight
  weatherGrid?: WeatherGrid | null;  // Weather grid points for visualization
}

// Component to handle map clicks
function MapClickHandler({ 
  startPoint, 
  onStartPointChange, 
  onEndPointChange 
}: { 
  startPoint: Coordinates | null;
  onStartPointChange: (coords: Coordinates) => void;
  onEndPointChange: (coords: Coordinates) => void;
}) {
  useMapEvents({
    click: (e) => {
      const coords: Coordinates = { lat: e.latlng.lat, lng: e.latlng.lng };
      if (!startPoint) {
        onStartPointChange(coords);
      } else {
        onEndPointChange(coords);
      }
    },
  });
  return null;
}

// Component to update map center when user location is detected (only once)
function MapCenterUpdater({ center, shouldUpdate }: { center: LatLngExpression; shouldUpdate: boolean }) {
  const map = useMap();
  const hasUpdatedRef = useRef(false);
  
  useEffect(() => {
    // Only update once when shouldUpdate becomes true and we haven't updated yet
    if (shouldUpdate && !hasUpdatedRef.current) {
      map.setView(center, map.getZoom());
      hasUpdatedRef.current = true;
    }
  }, [map, center, shouldUpdate]);
  return null;
}

// Helper function to get color based on wind speed
// Green (low wind) -> Yellow -> Orange -> Red (high wind)
function getWindColor(windSpeed: number): string {
  // Wind speed ranges (in knots):
  // 0-10: Green (calm to light breeze)
  // 10-20: Yellow-green (moderate breeze)
  // 20-30: Orange (strong breeze)
  // 30+: Red (gale)
  
  if (windSpeed < 10) {
    // Green to yellow-green
    const ratio = windSpeed / 10;
    const r = Math.round(34 + (154 - 34) * ratio);
    const g = Math.round(197 + (205 - 197) * ratio);
    const b = Math.round(94 + (50 - 94) * ratio);
    return `rgba(${r}, ${g}, ${b}, 0.5)`;
  } else if (windSpeed < 20) {
    // Yellow-green to orange
    const ratio = (windSpeed - 10) / 10;
    const r = Math.round(154 + (249 - 154) * ratio);
    const g = Math.round(205 + (115 - 205) * ratio);
    const b = Math.round(50 + (22 - 50) * ratio);
    return `rgba(${r}, ${g}, ${b}, 0.5)`;
  } else if (windSpeed < 30) {
    // Orange to red
    const ratio = (windSpeed - 20) / 10;
    const r = Math.round(249 + (239 - 249) * ratio);
    const g = Math.round(115 + (68 - 115) * ratio);
    const b = Math.round(22 + (68 - 22) * ratio);
    return `rgba(${r}, ${g}, ${b}, 0.5)`;
  } else {
    // Red (high wind)
    return 'rgba(239, 68, 68, 0.5)';
  }
}

// Component to render wind arrow as a custom marker
function WindArrowMarker({ 
  position, 
  windDirection, 
  windSpeed 
}: { 
  position: LatLngExpression; 
  windDirection: number; 
  windSpeed: number;
}) {
  // Smaller fixed arrow length
  const arrowLength = 14;
  const arrowWidth = 2;
  
  // Get color based on wind speed (with transparency)
  const arrowColor = getWindColor(windSpeed);
  
  // Create SVG arrow pointing in wind direction
  // Wind direction is where wind comes FROM, so arrow points in that direction
  const arrowSvg = `
    <svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg">
      <g transform="translate(14,14) rotate(${windDirection})">
        <line 
          x1="0" y1="0" 
          x2="0" y2="${arrowLength}" 
          stroke="${arrowColor}" 
          stroke-width="${arrowWidth}" 
          stroke-linecap="round"
        />
        <polygon 
          points="0,${arrowLength} -3,${arrowLength - 6} 3,${arrowLength - 6}" 
          fill="${arrowColor}"
        />
      </g>
    </svg>
  `;

  const arrowIcon = new DivIcon({
    className: 'wind-arrow-icon',
    html: arrowSvg,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });

  return (
    <Marker position={position} icon={arrowIcon}>
      <Popup>
        <div className="bg-slate-900 text-white rounded p-2">
          <p className="text-sm font-semibold">💨 Wind</p>
          <p className="text-xs">Direction: {windDirection.toFixed(0)}°</p>
          <p className="text-xs">Speed: {windSpeed.toFixed(1)} kt</p>
        </div>
      </Popup>
    </Marker>
  );
}

export default function Map({
  startPoint,
  endPoint,
  routes,
  selectedRouteIndex,
  onStartPointChange,
  onEndPointChange,
  highlightedNoGoZone,
  highlightedWaypoint,
  weatherGrid,
}: MapProps) {
  // State for showing/hiding weather grid
  const [showGrid, setShowGrid] = useState(true);
  
  // State for selected hour index
  const [selectedHourIndex, setSelectedHourIndex] = useState(0);
  
  // State for user's detected location
  const [userLocation, setUserLocation] = useState<Coordinates | null>(null);
  const [hasInitialLocation, setHasInitialLocation] = useState(false);
  
  // Animation state
  const [isAnimating, setIsAnimating] = useState(false);
  const [animationWaypointIndex, setAnimationWaypointIndex] = useState(0);
  const animationIntervalRef = useRef<number | null>(null);
  
  // Default center: English Channel (good sailing area) - fallback
  const defaultCenter: LatLngExpression = [50.0, -2.0];
  const defaultZoom = 7;
  
  // Use user location if available, otherwise use default
  const mapCenter: LatLngExpression = userLocation 
    ? [userLocation.lat, userLocation.lng] 
    : defaultCenter;
  
  // Fetch user location on component mount (only once)
  useEffect(() => {
    getUserLocation()
      .then((location) => {
        if (location) {
          setUserLocation(location);
          setHasInitialLocation(true);
        }
      })
      .catch((error) => {
        console.error('Failed to get user location:', error);
      });
  }, []);

  // Convert waypoints to polyline format
  const getRoutePositions = (route: Route): LatLngExpression[] => {
    return route.waypoints.map(wp => [wp.position.lat, wp.position.lng] as LatLngExpression);
  };

  // Get available hours from weather grid
  const allHours = weatherGrid?.times || [];
  const gridPointsWithWeather = weatherGrid?.gridPointsWithWeather || [];

  // Filter hours to only show those within route waypoints timeframe
  const availableHours = (() => {
    if (allHours.length === 0) return [];
    
    // If we have a selected route, filter to its timeframe
    if (selectedRouteIndex !== null && routes[selectedRouteIndex]) {
      const route = routes[selectedRouteIndex];
      if (route.waypoints.length > 0) {
        const firstWaypoint = route.waypoints[0];
        const lastWaypoint = route.waypoints[route.waypoints.length - 1];
        
        try {
          const startTime = new Date(firstWaypoint.estimatedArrival);
          const endTime = new Date(lastWaypoint.estimatedArrival);
          
          // Filter hours that fall within the route timeframe
          return allHours.filter(timeStr => {
            const time = new Date(timeStr);
            return time >= startTime && time <= endTime;
          });
        } catch {
          // If parsing fails, return all hours
          return allHours;
        }
      }
    }
    
    // If no route selected, show all hours
    return allHours;
  })();

  // Helper function to find closest hour for a waypoint
  const findClosestHourIndex = (waypointTime: Date): number => {
    if (availableHours.length === 0) return 0;
    
    let closestIndex = 0;
    let minDiff = Math.abs(new Date(availableHours[0]).getTime() - waypointTime.getTime());
    
    for (let i = 1; i < availableHours.length; i++) {
      const hourTime = new Date(availableHours[i]);
      const diff = Math.abs(hourTime.getTime() - waypointTime.getTime());
      if (diff < minDiff) {
        minDiff = diff;
        closestIndex = i;
      }
    }
    
    return closestIndex;
  };

  // Update selected hour when waypoint is highlighted
  useEffect(() => {
    if (highlightedWaypoint !== null && highlightedWaypoint !== undefined && 
        selectedRouteIndex !== null && routes[selectedRouteIndex]) {
      const route = routes[selectedRouteIndex];
      const waypoint = route.waypoints[highlightedWaypoint];
      
      if (waypoint && availableHours.length > 0) {
        try {
          const waypointTime = new Date(waypoint.estimatedArrival);
          const closestIndex = findClosestHourIndex(waypointTime);
          setSelectedHourIndex(closestIndex);
          // Removed automatic grid showing - user controls it with toggle
        } catch (error) {
          console.error('Error finding closest hour for waypoint:', error);
        }
      }
    }
  }, [highlightedWaypoint, selectedRouteIndex, routes, availableHours]);

  // Animation effect - update waypoint and wind grid
  useEffect(() => {
    if (isAnimating && selectedRouteIndex !== null && routes[selectedRouteIndex]) {
      const route = routes[selectedRouteIndex];
      
      // Clear any existing interval
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
      }
      
      // Start animation
      animationIntervalRef.current = window.setInterval(() => {
        setAnimationWaypointIndex((prevIndex) => {
          const nextIndex = prevIndex + 1;
          
          // If we've reached the end, stop animation
          if (nextIndex >= route.waypoints.length) {
            setIsAnimating(false);
            return prevIndex;
          }
          
          // Update wind grid to match this waypoint's time
          const waypoint = route.waypoints[nextIndex];
          if (waypoint && availableHours.length > 0) {
            try {
              const waypointTime = new Date(waypoint.estimatedArrival);
              const closestIndex = findClosestHourIndex(waypointTime);
              setSelectedHourIndex(closestIndex);
            } catch (error) {
              console.error('Error updating wind grid during animation:', error);
            }
          }
          
          return nextIndex;
        });
      }, 1000); // 1 second per waypoint
      
      return () => {
        if (animationIntervalRef.current) {
          clearInterval(animationIntervalRef.current);
        }
      };
    } else {
      // Stop animation
      if (animationIntervalRef.current) {
        clearInterval(animationIntervalRef.current);
        animationIntervalRef.current = null;
      }
    }
  }, [isAnimating, selectedRouteIndex, routes, availableHours]);

  // Handle animation controls
  const handleToggleAnimation = () => {
    if (selectedRouteIndex === null || !routes[selectedRouteIndex]) return;
    
    if (isAnimating) {
      // Stop animation and reset
      setIsAnimating(false);
      setAnimationWaypointIndex(0);
    } else {
      // Start animation
      setShowGrid(true);
      setAnimationWaypointIndex(0);
      setIsAnimating(true);
    }
  };

  // Format time for display (same format as waypoint cards: YYYY-MM-DD HH:MM)
  const formatTime = (timeString: string): string => {
    try {
      const date = new Date(timeString);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}`;
    } catch {
      return timeString;
    }
  };

  return (
    <div className="h-full w-full rounded-xl overflow-hidden shadow-2xl border border-slate-700 relative">
      {/* Weather grid controls */}
      {weatherGrid && weatherGrid.gridPoints && weatherGrid.gridPoints.length > 0 && (
        <div className="absolute top-2 right-2 z-[1000] flex flex-col gap-2">
          {/* Apple-style toggle for grid visibility */}
          <div className="bg-slate-800/90 border border-slate-600 rounded-lg shadow-lg p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">🌐</span>
                <div className="text-white text-sm font-medium">Wind Grid</div>
              </div>
              {/* Apple-style toggle switch */}
              <button
                onClick={() => setShowGrid(!showGrid)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:ring-offset-slate-800 ${
                  showGrid ? 'bg-blue-500' : 'bg-slate-600'
                }`}
                role="switch"
                aria-checked={showGrid}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ease-in-out ${
                    showGrid ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>

          {/* Animation controls - only show when grid is open */}
          {showGrid && selectedRouteIndex !== null && routes[selectedRouteIndex] && routes[selectedRouteIndex].waypoints.length > 0 && (
            <div className="bg-slate-800/90 border border-slate-600 rounded-lg shadow-lg p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🎬</span>
                  <div className="text-white text-sm font-medium">Route Animation</div>
                </div>
                <button
                  onClick={handleToggleAnimation}
                  className={`px-3 py-1.5 text-white rounded text-sm font-medium transition-all shadow-lg hover:shadow-xl ${
                    isAnimating 
                      ? 'bg-gradient-to-r from-red-300 via-rose-400 to-pink-400 hover:from-red-400 hover:via-rose-500 hover:to-pink-500' 
                      : 'bg-gradient-to-r from-green-300 via-emerald-400 to-teal-400 hover:from-green-400 hover:via-emerald-500 hover:to-teal-500'
                  }`}
                  title={isAnimating ? "Stop animation" : "Play animation"}
                >
                  {isAnimating ? 'Stop' : 'Play'}
                </button>
              </div>
              
              {isAnimating && (
                <div className="mt-2 text-xs text-slate-300">
                  Waypoint {animationWaypointIndex + 1} / {routes[selectedRouteIndex].waypoints.length}
                </div>
              )}
            </div>
          )}

          {/* Time selector - only show when grid is visible */}
          {showGrid && availableHours.length > 0 && (
            <div className="bg-slate-800/90 border border-slate-600 rounded-lg shadow-lg p-2">
              <label className="text-white text-xs mb-1 block">Hour:</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSelectedHourIndex(Math.max(0, selectedHourIndex - 1))}
                  disabled={selectedHourIndex === 0}
                  className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded text-sm"
                >
                  ‹
                </button>
                <select
                  value={selectedHourIndex}
                  onChange={(e) => setSelectedHourIndex(Number(e.target.value))}
                  className="bg-slate-700 text-white text-xs px-2 py-1 rounded border border-slate-600 min-w-[180px]"
                >
                  {availableHours.map((time, idx) => (
                    <option key={idx} value={idx}>
                      {formatTime(time)}
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => setSelectedHourIndex(Math.min(availableHours.length - 1, selectedHourIndex + 1))}
                  disabled={selectedHourIndex === availableHours.length - 1}
                  className="px-2 py-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded text-sm"
                >
                  ›
                </button>
              </div>
              <div className="text-xs text-slate-400 mt-1">
                {selectedHourIndex + 1} / {availableHours.length}
              </div>
            </div>
          )}
          
          {/* Wind speed legend - only show when grid is visible */}
          {showGrid && (
            <div className="bg-slate-800/90 border border-slate-600 rounded-lg shadow-lg p-2">
              <label className="text-white text-xs mb-1 block font-semibold">Wind Speed:</label>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgb(34, 197, 94)' }}></div>
                  <span className="text-xs text-white">0-10 kt</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgb(154, 205, 50)' }}></div>
                  <span className="text-xs text-white">10-20 kt</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgb(249, 115, 22)' }}></div>
                  <span className="text-xs text-white">20-30 kt</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded" style={{ backgroundColor: 'rgb(239, 68, 68)' }}></div>
                  <span className="text-xs text-white">30+ kt</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
      <MapContainer
        center={mapCenter}
        zoom={defaultZoom}
        className="h-full w-full"
        style={{ background: '#0f172a' }}
      >
        {/* Map tiles - using CartoDB dark theme for nautical feel */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Update map center when user location is detected (only once on initial load) */}
        <MapCenterUpdater center={mapCenter} shouldUpdate={hasInitialLocation && userLocation !== null} />

        {/* Click handler for setting points */}
        <MapClickHandler
          startPoint={startPoint}
          onStartPointChange={onStartPointChange}
          onEndPointChange={onEndPointChange}
        />

        {/* Start marker - only show when no routes calculated */}
        {startPoint && routes.length === 0 && (
          <Marker position={[startPoint.lat, startPoint.lng]} icon={startIcon}>
            <Popup>
              <span className="font-semibold text-green-600">Start Point</span>
              <br />
              {startPoint.lat.toFixed(4)}, {startPoint.lng.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* End marker - only show when no routes calculated */}
        {endPoint && routes.length === 0 && (
          <Marker position={[endPoint.lat, endPoint.lng]} icon={endIcon}>
            <Popup>
              <span className="font-semibold text-red-600">End Point</span>
              <br />
              {endPoint.lat.toFixed(4)}, {endPoint.lng.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* Route polylines - render in two passes: unselected first, selected last (on top) */}
        {(() => {
          const polylines = [];
          
          // First pass: render all unselected routes
          routes.forEach((route, index) => {
            if (selectedRouteIndex === null || selectedRouteIndex !== index) {
              polylines.push(
                <Polyline
                  key={`route-unsel-${index}`}
                  positions={getRoutePositions(route)}
                  color={getRouteColor(index)}
                  weight={3}
                  opacity={selectedRouteIndex === null ? 0.8 : 0.25}
                />
              );
            }
          });
          
          // Second pass: render selected route last (on top)
          if (selectedRouteIndex !== null && routes[selectedRouteIndex]) {
            const route = routes[selectedRouteIndex];
            
            // During animation, only show route up to current waypoint
            const routePositions = isAnimating 
              ? getRoutePositions(route).slice(0, animationWaypointIndex + 1)
              : getRoutePositions(route);
            
            polylines.push(
              <Polyline
                key={`route-sel-${selectedRouteIndex}`}
                positions={routePositions}
                color={getRouteColor(selectedRouteIndex)}
                weight={6}
                opacity={1.0}
              />
            );
            
            // Third pass: render no-go zone violations as circles
            if (route.noGoZoneViolations && route.noGoZoneViolations.length > 0) {
              route.noGoZoneViolations.forEach((violation) => {
                const waypoint = route.waypoints[violation.segmentIndex];
                if (waypoint) {
                  const position: LatLngExpression = [waypoint.position.lat, waypoint.position.lng];
                  const isHighlighted = highlightedNoGoZone === violation.segmentIndex;
                  
                  polylines.push(
                    <Circle
                      key={`no-go-${selectedRouteIndex}-${violation.segmentIndex}`}
                      center={position}
                      radius={isHighlighted ? 2000 : 500}  // 2km vs 500m
                      pathOptions={{
                        color: '#ff0000',
                        fillColor: '#ff0000',
                        fillOpacity: isHighlighted ? 0.6 : 0.3,
                        weight: isHighlighted ? 3 : 1,
                      }}
                    >
                      <Popup>
                        <div className="bg-slate-900 text-white rounded p-2">
                          <p className="font-bold text-red-500">⚠️ NO-GO ZONE</p>
                          <p className="text-sm">Segment {violation.segmentIndex}</p>
                          <p className="text-sm">Heading: {violation.heading.toFixed(0)}°</p>
                          <p className="text-sm">Wind Angle: {violation.windAngle.toFixed(0)}°</p>
                        </div>
                      </Popup>
                    </Circle>
                  );
                }
              });
            }
            
            // Fourth pass: render waypoint markers
            route.waypoints.forEach((waypoint, wpIndex) => {
              // During animation, only show waypoints up to current animation index
              if (isAnimating && wpIndex > animationWaypointIndex) {
                return;
              }
              
              const position: LatLngExpression = [waypoint.position.lat, waypoint.position.lng];
              const isHighlighted = highlightedWaypoint === wpIndex || (isAnimating && wpIndex === animationWaypointIndex);
              const isStart = wpIndex === 0;
              const isEnd = wpIndex === route.waypoints.length - 1;
              
              polylines.push(
                <CircleMarker
                  key={`waypoint-${selectedRouteIndex}-${wpIndex}`}
                  center={position}
                  radius={isHighlighted ? 8 : 4}
                  pathOptions={{
                    color: isStart ? '#22c55e' : isEnd ? '#ef4444' : '#3b82f6',
                    fillColor: isStart ? '#22c55e' : isEnd ? '#ef4444' : '#3b82f6',
                    fillOpacity: isHighlighted ? 1.0 : 0.7,
                    weight: isHighlighted ? 3 : 2,
                  }}
                >
                  <Popup>
                    <div className="bg-slate-900 text-white rounded p-2">
                      <p className="font-bold text-blue-400">
                        Waypoint {wpIndex + 1}
                        {isStart && <span className="text-green-400 ml-2">🚩 Start</span>}
                        {isEnd && <span className="text-red-400 ml-2">🏁 End</span>}
                      </p>
                      <p className="text-sm">{waypoint.position.lat.toFixed(4)}°, {waypoint.position.lng.toFixed(4)}°</p>
                      {waypoint.heading !== null && !isStart && (
                        <p className="text-sm mt-1">
                          <span className="text-cyan-400">⛵ Boat Heading:</span> {waypoint.heading.toFixed(0)}°
                        </p>
                      )}
                      {waypoint.weather && (
                        <>
                          <p className="text-sm">
                            <span className="text-blue-300">💨 Wind From:</span> {waypoint.weather.windDirection.toFixed(0)}°
                          </p>
                          <p className="text-sm">Wind Speed: {waypoint.weather.windSpeed.toFixed(0)} kt</p>
                          <p className="text-sm">Waves: {waypoint.weather.waveHeight.toFixed(1)} m</p>
                        </>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              );
            });
          }
          
          return polylines;
        })()}

        {/* Weather grid points with wind arrows - show per hour */}
        {showGrid && gridPointsWithWeather.length > 0 && availableHours.length > 0 && gridPointsWithWeather.map((point, index) => {
          // Map selected hour index to the actual time string
          const selectedTime = availableHours[selectedHourIndex];
          if (!selectedTime) return null;
          
          // Find the weather data for this time
          const hourlyWeather = point.hourlyWeather.find(w => w.time === selectedTime);
          if (!hourlyWeather) return null;

          return (
            <WindArrowMarker
              key={`wind-arrow-${index}-${selectedHourIndex}`}
              position={[point.lat, point.lng]}
              windDirection={hourlyWeather.windDirection}
              windSpeed={hourlyWeather.windSpeed}
            />
          );
        })}
      </MapContainer>
    </div>
  );
}

