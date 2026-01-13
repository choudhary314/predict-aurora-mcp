# aurora_server.py
from fastmcp import FastMCP
import requests
from typing import Optional, Dict, Any, Tuple
from collections import OrderedDict
import time

# Initialize FastMCP server
mcp = FastMCP("Aurora Forecast")

# TTL + LRU Cache implementation
class TTLLRUCache:
    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str, ttl_seconds: int) -> Optional[Any]:
        if key not in self._cache:
            self._misses += 1
            return None
        
        entry = self._cache[key]
        age = time.time() - entry['timestamp']
        
        if age > ttl_seconds:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._cache.move_to_end(key)
        self._hits += 1
        return entry['data']
    
    def set(self, key: str, data: Any):
        if key in self._cache:
            del self._cache[key]
        
        self._cache[key] = {
            'data': data,
            'timestamp': time.time()
        }
        
        while len(self._cache) > self.max_size:
            self._cache.popitem(last=False)
    
    def clear(self):
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': f"{hit_rate:.1f}%",
            'keys': list(self._cache.keys())
        }

# Initialize cache
cache = TTLLRUCache(max_size=50)

# Cache TTL settings (seconds)
CACHE_TTL = {
    'location': 3600,        # 1 hour
    'ovation': 300,          # 5 minutes
    'kp_index': 180,         # 3 minutes
    'enlil': 3600,           # 1 hour
    'solar_probabilities': 3600,  # 1 hour
}

# Helper functions
def get_user_location() -> Optional[Dict]:
    """Get user location from IP with caching"""
    cache_key = 'user_location'
    cached = cache.get(cache_key, CACHE_TTL['location'])
    if cached:
        return cached

    errors = []

    # Provider 1: ipapi.co (can rate-limit)
    try:
        response = requests.get('https://ipapi.co/json/', timeout=5)
        data = response.json()
        if response.status_code == 200 and 'latitude' in data and 'longitude' in data:
            location = {
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', 'Unknown'),
                'country': data.get('country_name', data.get('country', 'Unknown'))
            }
            cache.set(cache_key, location)
            return location

        # Normalize common error payload shape
        if isinstance(data, dict) and data.get('error') is True:
            errors.append(f"ipapi.co: {data.get('reason', 'error')} ({data.get('message', 'no message')})")
        else:
            errors.append(f"ipapi.co: unexpected response (status={response.status_code})")
    except Exception as e:
        errors.append(f"ipapi.co: {e}")

    # Provider 2: ipwho.is (free, no key; supports selective fields)
    try:
        response = requests.get(
            'https://ipwho.is/?fields=success,message,latitude,longitude,city,region,country',
            timeout=5,
        )
        data = response.json()
        if data.get('success') is False:
            errors.append(f"ipwho.is: {data.get('message', 'error')}")
        elif 'latitude' in data and 'longitude' in data:
            location = {
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'city': data.get('city', 'Unknown'),
                'region': data.get('region', 'Unknown'),
                'country': data.get('country', 'Unknown')
            }
            cache.set(cache_key, location)
            return location
        else:
            errors.append(f"ipwho.is: unexpected response (status={response.status_code})")
    except Exception as e:
        errors.append(f"ipwho.is: {e}")

    raise Exception(
        "Could not determine location from IP. "
        + ("; ".join(errors) if errors else "No providers available.")
    )


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90 <= latitude <= 90:
        raise ValueError("Latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("Longitude must be between -180 and 180")


def resolve_location(
    latitude: Optional[float] = None, longitude: Optional[float] = None
) -> Tuple[float, float, str, Dict[str, Any]]:
    """Resolve coordinates from user input or (fallback) IP geolocation.

    Rules:
    - If both latitude and longitude are provided, use them (validated).
    - If only one is provided, ignore it and fall back to IP geolocation.
    - If neither is provided, fall back to IP geolocation.

    Returns:
        (lat, lon, display_name, meta)
    """

    has_lat = latitude is not None
    has_lon = longitude is not None

    # Use user-provided coordinates only when both are present
    if has_lat and has_lon:
        _validate_coordinates(latitude, longitude)
        return (
            float(latitude),
            float(longitude),
            f"{latitude:.2f}°, {longitude:.2f}°",
            {"source": "user", "note": None},
        )

    # Partial coordinates -> ignore and fall back to IP
    note = None
    if has_lat ^ has_lon:
        note = "Only one coordinate was provided; falling back to IP-based location."

    location = get_user_location()
    lat = float(location["latitude"])
    lon = float(location["longitude"])
    display_name = f"{location['city']}, {location['region']}, {location['country']}"
    return (
        lat,
        lon,
        display_name,
        {"source": "ip", "note": note, "location": location},
    )

def get_ovation_data() -> Optional[Dict]:
    """Fetch OVATION aurora data with caching"""
    cache_key = 'ovation_data'
    cached = cache.get(cache_key, CACHE_TTL['ovation'])
    if cached:
        return cached
    
    try:
        response = requests.get(
            'https://services.swpc.noaa.gov/json/ovation_aurora_latest.json',
            timeout=10
        )
        data = response.json()
        cache.set(cache_key, data)
        return data
    except Exception as e:
        raise Exception(f"Could not fetch OVATION data: {e}")

def get_kp_index() -> Optional[list]:
    """Fetch Kp index with caching"""
    cache_key = 'kp_index'
    cached = cache.get(cache_key, CACHE_TTL['kp_index'])
    if cached:
        return cached
    
    try:
        response = requests.get(
            'https://services.swpc.noaa.gov/json/planetary_k_index_1m.json',
            timeout=10
        )
        data = response.json()
        cache.set(cache_key, data)
        return data
    except Exception as e:
        raise Exception(f"Could not fetch Kp index: {e}")

def get_enlil_predictions() -> Optional[Dict]:
    """Fetch ENLIL solar wind predictions with caching"""
    cache_key = 'enlil_data'
    cached = cache.get(cache_key, CACHE_TTL['enlil'])
    if cached:
        return cached
    
    try:
        response = requests.get(
            'https://services.swpc.noaa.gov/json/enlil_time_series.json',
            timeout=15
        )
        data = response.json()
        cache.set(cache_key, data)
        return data
    except Exception as e:
        raise Exception(f"Could not fetch ENLIL data: {e}")

def get_solar_probabilities() -> Optional[Dict]:
    """Fetch solar flare probabilities with caching"""
    cache_key = 'solar_probabilities'
    cached = cache.get(cache_key, CACHE_TTL['solar_probabilities'])
    if cached:
        return cached
    
    try:
        response = requests.get(
            'https://services.swpc.noaa.gov/json/solar_probabilities.json',
            timeout=10
        )
        data = response.json()
        cache.set(cache_key, data)
        return data
    except Exception as e:
        raise Exception(f"Could not fetch solar probabilities: {e}")

def find_nearest_aurora_probability(lat: float, lon: float, ovation_data: dict) -> float:
    """Find nearest grid point aurora probability"""
    if 'coordinates' not in ovation_data:
        return 0.0
    
    min_distance = float('inf')
    nearest_probability = 0
    
    for point in ovation_data['coordinates']:
        point_lon, point_lat, probability = point
        distance = ((lat - point_lat)**2 + (lon - point_lon)**2)**0.5
        if distance < min_distance:
            min_distance = distance
            nearest_probability = probability
    
    return nearest_probability

def get_aurora_for_coordinates(lat: float, lon: float) -> Dict:
    """Get aurora data for specific coordinates with caching"""
    # Round coordinates to 0.5 degrees for cache efficiency
    rounded_lat = round(lat * 2) / 2
    rounded_lon = round(lon * 2) / 2
    cache_key = f'aurora_{rounded_lat}_{rounded_lon}'
    
    cached = cache.get(cache_key, CACHE_TTL['ovation'])
    if cached:
        return cached
    
    # Fetch fresh data
    ovation_data = get_ovation_data()
    kp_data = get_kp_index()
    
    probability = find_nearest_aurora_probability(lat, lon, ovation_data)
    latest_kp = kp_data[-1]['kp'] if kp_data else "Unknown"
    
    result = {
        'probability': probability,
        'kp': latest_kp,
        'latitude': lat,
        'longitude': lon
    }
    
    cache.set(cache_key, result)
    return result

# ============= FastMCP Tools =============

def _format_aurora_forecast(latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
    """Internal implementation for aurora forecast formatting."""
    lat, lon, display_name, meta = resolve_location(latitude, longitude)
    aurora_data = get_aurora_for_coordinates(lat, lon)

    result = f"""Aurora Forecast for {display_name}
Location: {lat:.2f}°, {lon:.2f}°

Current Aurora Probability: {aurora_data['probability']:.1f}%
Current Kp Index: {aurora_data['kp']}

Viewing Recommendation:
"""
    if aurora_data['probability'] > 50:
        result += "HIGH - Excellent aurora viewing conditions!"
    elif aurora_data['probability'] > 25:
        result += "MODERATE - Aurora may be visible with clear skies"
    else:
        result += "LOW - Aurora unlikely to be visible"
    
    if lat > 0 and lat < 55:
        result += "\n\nNote: Your latitude is quite far south. Aurora is typically visible above 60°N."

    if meta.get("note"):
        result += f"\n\nNote: {meta['note']}"

    return result


def _format_aurora_prediction(
    latitude: Optional[float] = None, longitude: Optional[float] = None, hours_ahead: int = 24
) -> str:
    """Internal implementation for aurora prediction formatting."""
    lat, lon, display_name, meta = resolve_location(latitude, longitude)
    enlil_data = get_enlil_predictions()
    solar_prob = get_solar_probabilities()
    _ = solar_prob  # currently unused; kept for future expansion

    # This is simplified - full implementation would parse ENLIL time series
    result = f"""Aurora Prediction for {display_name}
Location: {lat:.2f}°, {lon:.2f}°

Forecast Period: Next {hours_ahead} hours

Based on ENLIL solar wind model and solar activity forecasts:
- Solar wind data points available: {len(enlil_data)}
- Solar flare probabilities loaded

Note: Full prediction analysis requires parsing ENLIL time series data.
This would predict CME arrivals and geomagnetic storm timing.
"""

    if meta.get("note"):
        result += f"\nNote: {meta['note']}\n"
    return result

@mcp.tool()
def get_aurora_forecast_auto() -> str:
    """Get aurora forecast for your current location (detected from IP)"""
    # Backwards-compatible alias; new preferred tool is get_aurora_forecast()
    return _format_aurora_forecast()


@mcp.tool()
def get_aurora_forecast(latitude: Optional[float] = None, longitude: Optional[float] = None) -> str:
    """Get aurora forecast using provided coordinates, or IP-based location fallback.

    Args:
        latitude: Latitude in degrees (-90 to 90). Must be provided with longitude.
        longitude: Longitude in degrees (-180 to 180). Must be provided with latitude.
    """

    return _format_aurora_forecast(latitude, longitude)

@mcp.tool()
def get_current_kp_index() -> str:
    """Get current planetary K-index (geomagnetic activity level)"""
    kp_data = get_kp_index()
    latest = kp_data[-1]
    
    result = f"""Current Geomagnetic Activity (Kp Index)

Kp: {latest['kp']}
Time: {latest['time_tag']}

Scale:
0-2: Quiet
3-4: Unsettled
5: Minor storm (G1)
6: Moderate storm (G2)
7: Strong storm (G3)
8: Severe storm (G4)
9: Extreme storm (G5)

Higher Kp values mean better aurora visibility at lower latitudes.
"""
    return result

@mcp.tool()
def get_aurora_prediction(
    latitude: Optional[float] = None, longitude: Optional[float] = None, hours_ahead: int = 24
) -> str:
    """
    Get aurora predictions for the next 24-48 hours
    
    Args:
        latitude: Latitude in degrees (-90 to 90). Must be provided with longitude.
        longitude: Longitude in degrees (-180 to 180). Must be provided with latitude.
        hours_ahead: How many hours ahead to predict (default 24)
    """
    return _format_aurora_prediction(latitude, longitude, hours_ahead)

@mcp.tool()
def verify_my_location() -> str:
    """Check what location was detected from your IP address"""
    location = get_user_location()
    
    result = f"""Detected Location from IP Address:

City: {location['city']}
Region: {location['region']}
Country: {location['country']}
Coordinates: {location['latitude']:.2f}°, {location['longitude']:.2f}°

Note: IP geolocation is approximate (city-level accuracy).
If this is incorrect, use get_aurora_forecast with exact coordinates.
"""
    return result

@mcp.tool()
def get_cache_stats() -> str:
    """Show cache statistics including hit rate and current size"""
    stats = cache.stats()
    
    result = f"""Cache Statistics:

Size: {stats['size']}/{stats['max_size']} entries
Hit Rate: {stats['hit_rate']}
Hits: {stats['hits']}
Misses: {stats['misses']}

Cached Keys:
"""
    for key in stats['keys']:
        result += f"  - {key}\n"
    
    return result

@mcp.tool()
def clear_cache() -> str:
    """Clear all cached data to force fresh data fetch"""
    cache.clear()
    return "Cache cleared. Next requests will fetch fresh data from NOAA."

def main():
    mcp.run(transport="stdio")

# Run the server
if __name__ == "__main__":
    main()
