import type { Coordinates } from '../types';

/**
 * Attempts to get user's location using browser geolocation API
 * Falls back to IP-based geolocation if browser geolocation is denied/unavailable
 */
export async function getUserLocation(): Promise<Coordinates | null> {
  // First, try browser geolocation (more accurate)
  if ('geolocation' in navigator) {
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          timeout: 5000,
          maximumAge: 300000, // Cache for 5 minutes
        });
      });

      return {
        lat: position.coords.latitude,
        lng: position.coords.longitude,
      };
    } catch (error) {
      // User denied permission or geolocation failed
      console.log('Browser geolocation not available, trying IP geolocation...', error);
    }
  }

  // Fallback to IP-based geolocation
  try {
    const response = await fetch('https://ipapi.co/json/');
    if (!response.ok) {
      throw new Error('IP geolocation service unavailable');
    }

    const data = await response.json();
    
    // Check if we got valid coordinates
    if (data.latitude && data.longitude) {
      return {
        lat: data.latitude,
        lng: data.longitude,
      };
    }
  } catch (error) {
    console.error('Failed to get location from IP:', error);
  }

  return null;
}

