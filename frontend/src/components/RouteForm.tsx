import type { Coordinates, BoatType } from '../types';
import DateTimePicker from './DateTimePicker';

interface RouteFormProps {
  startPoint: Coordinates | null;
  endPoint: Coordinates | null;
  boatType: BoatType;
  departureTime: string;
  loading: boolean;
  hasRoutes: boolean;
  onBoatTypeChange: (type: BoatType) => void;
  onDepartureTimeChange: (time: string) => void;
  onCalculate: () => void;
  onClear: () => void;
}

const BOAT_OPTIONS: { value: BoatType; label: string; icon: string; description: string }[] = [
  { 
    value: 'sailboat', 
    label: 'Sailboat', 
    icon: '⛵', 
    description: 'Wind-powered, 5-8 knots avg' 
  },
  { 
    value: 'motorboat', 
    label: 'Motorboat', 
    icon: '🚤', 
    description: 'Engine-powered, 15-25 knots' 
  },
  { 
    value: 'catamaran', 
    label: 'Catamaran', 
    icon: '🛥️', 
    description: 'Twin-hull, 8-12 knots avg' 
  },
];

export default function RouteForm({
  startPoint,
  endPoint,
  boatType,
  departureTime,
  loading,
  hasRoutes,
  onBoatTypeChange,
  onDepartureTimeChange,
  onCalculate,
  onClear,
}: RouteFormProps) {
  const canCalculate = startPoint && endPoint && !loading;
  const showReset = hasRoutes && !loading;

  return (
    <div className="bg-slate-800/80 backdrop-blur-sm rounded-xl p-5 shadow-xl border border-slate-700">
      {/* Header */}
      <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
        <span className="text-2xl">🧭</span>
        Route Planner
      </h2>

      {/* Coordinates display */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-slate-900/50 rounded-lg p-3">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">Start</p>
          {startPoint ? (
            <p className="text-emerald-400 font-mono text-sm">
              {startPoint.lat.toFixed(3)}, {startPoint.lng.toFixed(3)}
            </p>
          ) : (
            <p className="text-slate-500 text-sm">Not set</p>
          )}
        </div>
        <div className="bg-slate-900/50 rounded-lg p-3">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">End</p>
          {endPoint ? (
            <p className="text-amber-400 font-mono text-sm">
              {endPoint.lat.toFixed(3)}, {endPoint.lng.toFixed(3)}
            </p>
          ) : (
            <p className="text-slate-500 text-sm">Not set</p>
          )}
        </div>
      </div>

      {/* Departure time selector */}
      <div className="mb-4">
        <label className="text-xs text-slate-400 uppercase tracking-wide mb-2 block font-medium">
          Departure Time
        </label>
        <DateTimePicker
          value={departureTime}
          onChange={onDepartureTimeChange}
          disabled={loading}
        />
        <p className="text-xs text-slate-500/80 mt-2 ml-1">
          Weather forecast will be based on this time
        </p>
      </div>

      {/* Boat type selector */}
      <div className="mb-4">
        <p className="text-xs text-slate-400 uppercase tracking-wide mb-2">Boat Type</p>
        <div className="space-y-2">
          {BOAT_OPTIONS.map((option) => (
            <button
              key={option.value}
              onClick={() => onBoatTypeChange(option.value)}
              className={`w-full p-3 rounded-lg text-left transition-all duration-200 flex items-center gap-3
                ${boatType === option.value
                  ? 'bg-sky-600 text-white shadow-lg shadow-sky-600/30'
                  : 'bg-slate-900/50 text-slate-300 hover:bg-slate-700'
                }`}
            >
              <span className="text-2xl">{option.icon}</span>
              <div>
                <p className="font-semibold">{option.label}</p>
                <p className={`text-xs ${boatType === option.value ? 'text-sky-200' : 'text-slate-500'}`}>
                  {option.description}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Action buttons */}
      <div className="flex gap-2">
        <button
          onClick={showReset ? onClear : onCalculate}
          disabled={!showReset && !canCalculate}
          className={`flex-1 py-3 px-4 rounded-lg font-semibold transition-all duration-200 flex items-center justify-center gap-2
            ${showReset
              ? 'bg-gradient-to-r from-cyan-500 to-emerald-500 text-white hover:from-cyan-400 hover:to-emerald-400 shadow-lg text-lg'
              : canCalculate
                ? 'bg-gradient-to-r from-cyan-500 to-emerald-500 text-white hover:from-cyan-400 hover:to-emerald-400 shadow-lg'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            }`}
        >
          {loading ? (
            <>
              <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Calculating...
            </>
          ) : showReset ? (
            <span className="flex items-center justify-center w-full gap-2">
              <span className="text-xl">🔄</span>
              <span>Reset</span>
              <span className="text-xl invisible">🔄</span>
            </span>
          ) : (
            <>
              <span>🚀</span>
              Calculate Routes
            </>
          )}
        </button>
      </div>
    </div>
  );
}

