import type { Route } from '../types';

interface RouteCardsProps {
  routes: Route[];
  selectedIndex: number | null;
  onSelectRoute: (index: number) => void;
}

// Route type to display info
const ROUTE_INFO: Record<string, { color: string; bgColor: string; borderColor: string }> = {
  direct: { 
    color: 'text-blue-400', 
    bgColor: 'bg-blue-500/10', 
    borderColor: 'border-blue-500' 
  },
  port: { 
    color: 'text-green-400', 
    bgColor: 'bg-green-500/10', 
    borderColor: 'border-green-500' 
  },
  starboard: { 
    color: 'text-orange-400', 
    bgColor: 'bg-orange-500/10', 
    borderColor: 'border-orange-500' 
  },
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
  isSelected, 
  onSelect 
}: { 
  route: Route; 
  index: number; 
  isSelected: boolean;
  onSelect: () => void;
}) {
  const info = ROUTE_INFO[route.type] || ROUTE_INFO.direct;
  const isRecommended = index === 0; // First route (highest score) is recommended

  return (
    <div
      onClick={onSelect}
      className={`relative p-4 rounded-xl cursor-pointer transition-all duration-300 border-2
        ${isSelected 
          ? `${info.bgColor} ${info.borderColor} shadow-lg scale-[1.02]` 
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

      {/* Warnings */}
      {route.warnings.length > 0 && (
        <div className="mb-3">
          {route.warnings.map((warning, i) => (
            <div key={i} className="flex items-start gap-2 text-amber-400 text-xs bg-amber-500/10 rounded p-2 mb-1">
              <span>⚠️</span>
              <span>{warning}</span>
            </div>
          ))}
        </div>
      )}

      {/* Pros & Cons (shown when selected) */}
      {isSelected && (
        <div className="mt-3 pt-3 border-t border-slate-700 space-y-2">
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
  );
}

export default function RouteCards({ routes, selectedIndex, onSelectRoute }: RouteCardsProps) {
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

  // Sort routes by score (highest first)
  const sortedRoutes = [...routes].sort((a, b) => b.score - a.score);

  return (
    <div className="space-y-3">
      <h3 className="text-white font-semibold flex items-center gap-2">
        <span>📊</span>
        Route Options
        <span className="text-slate-500 text-sm font-normal">({routes.length} routes)</span>
      </h3>
      
      {sortedRoutes.map((route, index) => (
        <RouteCard
          key={route.type}
          route={route}
          index={index}
          isSelected={selectedIndex !== null && routes[selectedIndex]?.type === route.type}
          onSelect={() => {
            // Find the original index in the routes array
            const originalIndex = routes.findIndex(r => r.type === route.type);
            onSelectRoute(originalIndex);
          }}
        />
      ))}
    </div>
  );
}

