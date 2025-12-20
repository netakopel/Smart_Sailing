import { useState, useRef, useEffect } from 'react';

interface DateTimePickerProps {
  value: string; // Format: YYYY-MM-DDTHH:mm
  onChange: (value: string) => void;
  disabled?: boolean;
}

export default function DateTimePicker({ value, onChange, disabled }: DateTimePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedDate, setSelectedDate] = useState(() => {
    const date = value ? new Date(value) : new Date();
    return {
      year: date.getFullYear(),
      month: date.getMonth(),
      day: date.getDate(),
      hour: date.getHours(),
      minute: date.getMinutes(),
    };
  });
  const pickerRef = useRef<HTMLDivElement>(null);

  // Update selectedDate when value prop changes
  useEffect(() => {
    if (value) {
      const date = new Date(value);
      setSelectedDate({
        year: date.getFullYear(),
        month: date.getMonth(),
        day: date.getDate(),
        hour: date.getHours(),
        minute: date.getMinutes(),
      });
    }
  }, [value]);

  // Close picker when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const formatDisplayValue = () => {
    if (!value) return '';
    const date = new Date(value);
    const month = date.toLocaleString('en-US', { month: 'short' });
    const day = date.getDate();
    const year = date.getFullYear();
    const hours = date.getHours();
    const minutes = date.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    const displayHours = hours % 12 || 12;
    const displayMinutes = minutes.toString().padStart(2, '0');
    return `${month} ${day}, ${year} at ${displayHours}:${displayMinutes} ${ampm}`;
  };

  const handleDateChange = (field: 'year' | 'month' | 'day' | 'hour' | 'minute', delta: number) => {
    setSelectedDate((prev) => {
      const newDate = { ...prev };
      
      if (field === 'year') {
        newDate.year = Math.max(2020, Math.min(2100, prev.year + delta));
      } else if (field === 'month') {
        let newMonth = prev.month + delta;
        if (newMonth < 0) {
          newMonth = 11;
          newDate.year = Math.max(2020, prev.year - 1);
        } else if (newMonth > 11) {
          newMonth = 0;
          newDate.year = Math.min(2100, prev.year + 1);
        }
        newDate.month = newMonth;
        // Adjust day if it's invalid for the new month
        const daysInMonth = new Date(newDate.year, newDate.month + 1, 0).getDate();
        if (newDate.day > daysInMonth) {
          newDate.day = daysInMonth;
        }
      } else if (field === 'day') {
        const daysInMonth = new Date(prev.year, prev.month + 1, 0).getDate();
        newDate.day = Math.max(1, Math.min(daysInMonth, prev.day + delta));
      } else if (field === 'hour') {
        newDate.hour = ((prev.hour + delta) % 24 + 24) % 24;
      } else if (field === 'minute') {
        newDate.minute = ((prev.minute + delta) % 60 + 60) % 60;
      }

      // Create new date and update value
      const newDateTime = new Date(
        newDate.year,
        newDate.month,
        newDate.day,
        newDate.hour,
        newDate.minute
      );
      
      // Format as YYYY-MM-DDTHH:mm
      const year = newDateTime.getFullYear();
      const month = String(newDateTime.getMonth() + 1).padStart(2, '0');
      const day = String(newDateTime.getDate()).padStart(2, '0');
      const hours = String(newDateTime.getHours()).padStart(2, '0');
      const minutes = String(newDateTime.getMinutes()).padStart(2, '0');
      const formattedValue = `${year}-${month}-${day}T${hours}:${minutes}`;
      
      onChange(formattedValue);
      return newDate;
    });
  };

  const months = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const daysInMonth = new Date(selectedDate.year, selectedDate.month + 1, 0).getDate();
  const monthName = months[selectedDate.month];

  return (
    <div className="relative" ref={pickerRef}>
      {/* Input field */}
      <div
        onClick={() => !disabled && setIsOpen(!isOpen)}
        className={`
          w-full pl-12 pr-4 py-3.5 rounded-xl bg-slate-900/60 text-white border border-slate-700/50 
          focus-within:border-sky-500/50 focus-within:bg-slate-900/80 focus-within:ring-2 focus-within:ring-sky-500/30 
          transition-all duration-200 backdrop-blur-sm cursor-pointer
          ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-slate-600/50'}
        `}
      >
        <div className="absolute left-4 top-1/2 -translate-y-1/2 pointer-events-none z-10">
          <svg 
            className="w-5 h-5 text-slate-400 transition-colors" 
            fill="none" 
            stroke="currentColor" 
            viewBox="0 0 24 24"
          >
            <path 
              strokeLinecap="round" 
              strokeLinejoin="round" 
              strokeWidth={2} 
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" 
            />
          </svg>
        </div>
        <div className="text-white">
          {formatDisplayValue() || 'Select date and time'}
        </div>
      </div>

      {/* Custom Picker Modal */}
      {isOpen && !disabled && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-40"
            onClick={() => setIsOpen(false)}
          />
          
          {/* Picker - positioned above Route Planner */}
          <div className="fixed top-16 left-4 w-[calc((min(100vw,1280px)-3rem-3rem)/3-2rem)] max-w-sm bg-slate-800/95 backdrop-blur-xl rounded-2xl shadow-2xl border border-slate-700/50 z-50 overflow-hidden">
            <div className="p-4">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-white">Select Date & Time</h3>
                <button
                  onClick={() => setIsOpen(false)}
                  className="w-8 h-8 rounded-full bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors"
                >
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Date Picker */}
              <div className="mb-4">
                <div className="text-base text-slate-400 mb-2 font-medium">Date</div>
                <div className="flex flex-col gap-3">
                  {/* Year */}
                  <div className="w-full opacity-60">
                    <div className="text-sm text-slate-500 mb-1.5 font-medium">Year</div>
                    <div className="w-full text-center py-1.5 px-2 rounded-xl bg-slate-900/30 text-slate-400 font-medium text-sm">
                      {selectedDate.year}
                    </div>
                  </div>

                  {/* Month */}
                  <div className="w-full opacity-60">
                    <div className="text-sm text-slate-500 mb-1.5 font-medium">Month</div>
                    <div className="w-full text-center py-1.5 px-2 rounded-xl bg-slate-900/30 text-slate-400 font-medium text-sm">
                      {monthName}
                    </div>
                  </div>
                  
                  {/* Joke/Explanation */}
                  <div className="mt-1 mb-2 p-2 bg-slate-900/40 rounded-lg border border-slate-700/30">
                    <p className="text-xs text-slate-400 italic text-center">
                      ⏰ Weather forecasting is only accurate for the current year and month. 
                      <br />
                      Sorry, we can't predict next year's weather... yet! 😅
                    </p>
                  </div>

                  {/* Day */}
                  <div className="w-full">
                    <div className="text-sm text-slate-500 mb-1.5 font-medium">Day</div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleDateChange('day', -1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <div className="flex-1 text-center py-1.5 px-2 rounded-xl bg-slate-900/50 text-white font-medium text-sm min-w-0">
                        {selectedDate.day}
                      </div>
                      <button
                        onClick={() => handleDateChange('day', 1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Time Picker */}
              <div className="mb-3">
                <div className="text-base text-slate-400 mb-2 font-medium">Time</div>
                <div className="flex items-center gap-3">
                  {/* Hour */}
                  <div className="flex-1">
                    <div className="text-sm text-slate-500 mb-1.5 font-medium">Hour</div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleDateChange('hour', -1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <div className="flex-1 text-center py-1.5 px-2 rounded-xl bg-slate-900/50 text-white font-medium text-sm min-w-0">
                        {String(selectedDate.hour).padStart(2, '0')}
                      </div>
                      <button
                        onClick={() => handleDateChange('hour', 1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </div>

                  <div className="text-xl text-slate-600 pt-5">:</div>

                  {/* Minute */}
                  <div className="flex-1">
                    <div className="text-sm text-slate-500 mb-1.5 font-medium">Minute</div>
                    <div className="flex items-center gap-1.5">
                      <button
                        onClick={() => handleDateChange('minute', -1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                        </svg>
                      </button>
                      <div className="flex-1 text-center py-1.5 px-2 rounded-xl bg-slate-900/50 text-white font-medium text-sm min-w-0">
                        {String(selectedDate.minute).padStart(2, '0')}
                      </div>
                      <button
                        onClick={() => handleDateChange('minute', 1)}
                        className="w-8 h-8 rounded-lg bg-slate-700/50 hover:bg-slate-700 flex items-center justify-center transition-colors flex-shrink-0"
                      >
                        <svg className="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Done Button */}
              <button
                onClick={() => setIsOpen(false)}
                className="w-full py-3 rounded-xl bg-gradient-to-r from-sky-500 to-cyan-500 text-white font-semibold hover:from-sky-400 hover:to-cyan-400 transition-all shadow-lg shadow-sky-500/30"
              >
                Done
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

