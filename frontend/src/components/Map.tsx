import { MapContainer, TileLayer, Marker, Polyline, useMapEvents, Popup } from 'react-leaflet';
import { Icon, LatLngExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import type { Coordinates, Route } from '../types';

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

// Route colors
const ROUTE_COLORS: Record<string, string> = {
  direct: '#3b82f6',    // Blue
  port: '#22c55e',      // Green
  starboard: '#f97316', // Orange
};

interface MapProps {
  startPoint: Coordinates | null;
  endPoint: Coordinates | null;
  routes: Route[];
  selectedRouteIndex: number | null;
  onStartPointChange: (coords: Coordinates) => void;
  onEndPointChange: (coords: Coordinates) => void;
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

export default function Map({
  startPoint,
  endPoint,
  routes,
  selectedRouteIndex,
  onStartPointChange,
  onEndPointChange,
}: MapProps) {
  // Default center: English Channel (good sailing area)
  const defaultCenter: LatLngExpression = [50.0, -2.0];
  const defaultZoom = 7;

  // Convert waypoints to polyline format
  const getRoutePositions = (route: Route): LatLngExpression[] => {
    return route.waypoints.map(wp => [wp.position.lat, wp.position.lng] as LatLngExpression);
  };

  return (
    <div className="h-full w-full rounded-xl overflow-hidden shadow-2xl border border-slate-700">
      <MapContainer
        center={defaultCenter}
        zoom={defaultZoom}
        className="h-full w-full"
        style={{ background: '#0f172a' }}
      >
        {/* Map tiles - using CartoDB dark theme for nautical feel */}
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
        />

        {/* Click handler for setting points */}
        <MapClickHandler
          startPoint={startPoint}
          onStartPointChange={onStartPointChange}
          onEndPointChange={onEndPointChange}
        />

        {/* Start marker */}
        {startPoint && (
          <Marker position={[startPoint.lat, startPoint.lng]} icon={startIcon}>
            <Popup>
              <span className="font-semibold text-green-600">Start Point</span>
              <br />
              {startPoint.lat.toFixed(4)}, {startPoint.lng.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* End marker */}
        {endPoint && (
          <Marker position={[endPoint.lat, endPoint.lng]} icon={endIcon}>
            <Popup>
              <span className="font-semibold text-red-600">End Point</span>
              <br />
              {endPoint.lat.toFixed(4)}, {endPoint.lng.toFixed(4)}
            </Popup>
          </Marker>
        )}

        {/* Route polylines */}
        {routes.map((route, index) => (
          <Polyline
            key={route.type}
            positions={getRoutePositions(route)}
            color={ROUTE_COLORS[route.type] || '#ffffff'}
            weight={selectedRouteIndex === index ? 5 : 3}
            opacity={selectedRouteIndex === null || selectedRouteIndex === index ? 0.9 : 0.3}
          />
        ))}
      </MapContainer>
    </div>
  );
}

