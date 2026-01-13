# predict-aurora-mcp

An MCP server (FastMCP) that provides aurora forecast tools using NOAA SWPC data.

## Location resolution behavior

Forecast/prediction tools follow this rule:

- If **both** `latitude` and `longitude` are provided, those coordinates are used.
- Otherwise, the server **falls back to IP-based geolocation**.
- If only one coordinate is provided, it’s ignored and IP-based geolocation is used.

IP geolocation uses (in order):

1. `ipapi.co` (may rate-limit)
2. `ipwho.is` (fallback)

## Tools

### `get_aurora_forecast(latitude?: float, longitude?: float)`
Returns the current aurora probability near the resolved coordinates plus current Kp index.

### `get_aurora_forecast_auto()`
Backwards-compatible alias for `get_aurora_forecast()`.

### `get_aurora_prediction(latitude?: float, longitude?: float, hours_ahead: int = 24)`
Returns a (currently simplified) aurora prediction summary for the next N hours.

### `verify_my_location()`
Shows the location detected from your IP.

### `get_current_kp_index()`
Shows the latest planetary Kp index reading.

### Cache tools
- `get_cache_stats()`
- `clear_cache()`

## Running

If installed as a package:

```bash
aurora
```

This runs the MCP server over stdio.

## License

Source-available for personal/internal use; no redistribution. See [LICENSE](./LICENSE).
