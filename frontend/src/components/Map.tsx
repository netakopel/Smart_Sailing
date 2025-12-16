import { MapContainer, TileLayer, Marker, Polyline, Circle, useMapEvents, Popup } from 'react-leaflet';
import { Icon, type LatLngExpression } from 'leaflet';
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
  highlightedNoGoZone,
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
            polylines.push(
              <Polyline
                key={`route-sel-${selectedRouteIndex}`}
                positions={getRoutePositions(route)}
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
          }
          
          return polylines;
        })()}
      </MapContainer>
    </div>
  );
}

