import type { Route } from '../types';

interface RouteCardsProps {
  routes: Route[];
  selectedIndex: number | null;
  onSelectRoute: (index: number) => void;
}

// Color palette for routes - matches Map.tsx
const ROUTE_COLOR_CLASSES = [
  { color: 'text-blue-400', bgColor: 'bg-blue-500/10', borderColor: 'border-blue-500' },      // Blue
  { color: 'text-green-400', bgColor: 'bg-green-500/10', borderColor: 'border-green-500' },   // Green
  { color: 'text-orange-400', bgColor: 'bg-orange-500/10', borderColor: 'border-orange-500' },// Orange
  { color: 'text-purple-400', bgColor: 'bg-purple-500/10', borderColor: 'border-purple-500' },// Purple
  { color: 'text-pink-400', bgColor: 'bg-pink-500/10', borderColor: 'border-pink-500' },      // Pink
  { color: 'text-teal-400', bgColor: 'bg-teal-500/10', borderColor: 'border-teal-500' },      // Teal
  { color: 'text-amber-400', bgColor: 'bg-amber-500/10', borderColor: 'border-amber-500' },   // Amber
  { color: 'text-red-400', bgColor: 'bg-red-500/10', borderColor: 'border-red-500' },         // Red
  { color: 'text-cyan-400', bgColor: 'bg-cyan-500/10', borderColor: 'border-cyan-500' },      // Cyan
  { color: 'text-violet-400', bgColor: 'bg-violet-500/10', borderColor: 'border-violet-500' },// Violet
];

// Helper to get color by index
const getRouteColorClass = (index: number) => {
  return ROUTE_COLOR_CLASSES[index % ROUTE_COLOR_CLASSES.length];
};

function ScoreBadge({ score }: { score: number }) {
  let colorClass = 'bg-red-500';
  if (score >= 80) colorClass = 'bg-emerald-500';
  else if (score >= 60) colorClass = 'bg-yellow-500';
  else if (score >= 40) colorClass = 'bg-orange-500';

  return (
    <div className={`${colorClass} text-white font-bold text-lg px-3 py-1 rounded-full shadow-lg`}>
      {score}
    </div>
  );
}

function RouteCard({ 
  route, 
  index, 
  colorIndex,
  isSelected, 
  onSelect,
  onNoGoZoneClick
}: { 
  route: Route; 
  index: number;
  colorIndex: number;
  isSelected: boolean;
  onSelect: () => void;
  onNoGoZoneClick?: (segmentIndex: number) => void;
}) {
  const info = getRouteColorClass(colorIndex);
  const isRecommended = index === 0; // First route (highest score) is recommended

  return (
    <div
      onClick={onSelect}
      className={`relative p-4 rounded-xl cursor-pointer transition-all duration-300 border-2 flex flex-col
        ${isSelected 
          ? `${info.bgColor} ${info.borderColor} shadow-lg scale-[1.01]` 
          : 'bg-slate-800/60 border-slate-700 hover:border-slate-500'
        }`}
    >
      {/* Recommended badge */}
      {isRecommended && (
        <div className="absolute -top-2 -right-2 bg-gradient-to-r from-amber-400 to-orange-500 text-slate-900 text-xs font-bold px-2 py-1 rounded-full shadow-lg">
          ⭐ BEST
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className={`font-bold text-lg ${info.color}`}>{route.name}</h3>
          <p className="text-slate-400 text-sm">{route.estimatedTime}</p>
        </div>
        <ScoreBadge score={route.score} />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-sm">
        <div className="bg-slate-900/50 rounded-lg p-2">
          <p className="text-slate-500 text-xs">Distance</p>
          <p className="text-white font-semibold">{route.distance.toFixed(1)} km</p>
        </div>
        <div className="bg-slate-900/50 rounded-lg p-2">
          <p className="text-slate-500 text-xs">Waypoints</p>
          <p className="text-white font-semibold">{route.waypoints.length}</p>
        </div>
      </div>

      {/* Scrollable content area for warnings and pros/cons */}
      <div className={`overflow-y-auto ${isSelected ? 'max-h-48' : 'max-h-32'}`}>
        {/* No-Go Zone Warnings (special handling) */}
        {(() => {
          const violations = (route as any).noGoZoneViolations;
          return violations && violations.length > 0 && (
          <div className="mb-3 space-y-1">
            <p className="text-red-400 text-xs font-semibold mb-1">🔴 NO-GO ZONES ({violations.length})</p>
            {violations.map((violation: any, i: number) => (
              <button
                key={i}
                onClick={() => {
                  console.log('Clicked no-go zone:', violation.segmentIndex);
                  onNoGoZoneClick?.(violation.segmentIndex);
                }}
                className="w-full text-left flex items-start gap-2 text-red-300 text-xs bg-red-500/15 hover:bg-red-500/25 rounded p-2 cursor-pointer transition-colors"
              >
                <span className="shrink-0">📍</span>
                <span>Segment {violation.segmentIndex}: Heading {violation.heading.toFixed(0)}° / Wind {violation.windAngle.toFixed(0)}°</span>
              </button>
            ))}
          </div>
        );
        })()}

        {/* Regular Warnings */}
        {route.warnings.length > 0 && (
          <div className="mb-3 space-y-1">
            {route.warnings.map((warning, i) => (
              <div key={i} className="flex items-start gap-2 text-amber-400 text-xs bg-amber-500/10 rounded p-2">
                <span className="shrink-0">⚠️</span>
                <span>{warning}</span>
              </div>
            ))}
          </div>
        )}

        {/* Pros & Cons (shown when selected) */}
        {isSelected && (
          <div className="pt-3 border-t border-slate-700 space-y-2">
            {route.pros.length > 0 && (
              <div>
                <p className="text-emerald-400 text-xs font-semibold mb-1">✓ Advantages</p>
                {route.pros.map((pro, i) => (
                  <p key={i} className="text-slate-300 text-xs ml-3">• {pro}</p>
                ))}
              </div>
            )}
            {route.cons.length > 0 && (
              <div>
                <p className="text-rose-400 text-xs font-semibold mb-1">✗ Concerns</p>
                {route.cons.map((con, i) => (
                  <p key={i} className="text-slate-300 text-xs ml-3">• {con}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

interface RouteCardsPropsWithCallbacks extends RouteCardsProps {
  onNoGoZoneClick?: (routeIndex: number, segmentIndex: number) => void;
}

export default function RouteCards({ routes, selectedIndex, onSelectRoute, onNoGoZoneClick }: RouteCardsPropsWithCallbacks) {
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

  // Sort routes by score (highest first), but keep track of original indices
  const sortedRoutesWithIndices = routes
    .map((route, originalIndex) => ({ route, originalIndex }))
    .sort((a, b) => b.route.score - a.route.score);

  return (
    <div className="space-y-3">
      <h3 className="text-white font-semibold flex items-center gap-2">
        <span>📊</span>
        Route Options
        <span className="text-slate-500 text-sm font-normal">({routes.length} routes)</span>
      </h3>
      
      <div className="flex flex-col gap-3 max-h-[calc(100vh-200px)] overflow-y-auto pr-2">
        {sortedRoutesWithIndices.map(({ route, originalIndex }, sortedIndex) => (
          <div key={`route-${originalIndex}`} className="w-full">
            <RouteCard
              route={route}
              index={sortedIndex}
              colorIndex={originalIndex}
              isSelected={selectedIndex === originalIndex}
              onSelect={() => onSelectRoute(originalIndex)}
              onNoGoZoneClick={(segmentIndex) => onNoGoZoneClick?.(originalIndex, segmentIndex)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

