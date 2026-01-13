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

### Run locally with `uvx` (simple)

From the repo root:

```bash
uvx --from . aurora
```

From anywhere (absolute path):

```bash
uvx --from /ABSOLUTE/PATH/TO/predict-aurora-mcp aurora
```

The server runs over **stdio** (the standard MCP pattern). Your MCP client will
start it and communicate over stdin/stdout.

### Add to Claude Desktop (uvx)

Add an MCP server with:

- `command`: `uvx`
- `args`: `["--from", "/ABSOLUTE/PATH/TO/predict-aurora-mcp", "aurora"]`

Example (insert under `mcpServers`):

```json
{
  "Aurora_predict": {
    "command": "uvx",
    "args": [
      "--from",
      "/ABSOLUTE/PATH/TO/predict-aurora-mcp",
      "aurora"
    ]
  }
}
```

### Add to Cline (uvx)

In Cline’s MCP Servers UI, add a server with:

- **Command**: `uvx`
- **Args**: `--from /ABSOLUTE/PATH/TO/predict-aurora-mcp aurora`

---

If installed as a package:

```bash
aurora
```

This runs the MCP server over stdio.

## License

Source-available for personal/internal use; no redistribution. See [LICENSE](./LICENSE).
