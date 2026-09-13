"""Provider-independent map layer configuration for RF Finder.

The map renderer is deliberately separated from RF evidence.  Providers only
supply geographic context; RF observations remain application-owned overlays.
Environment variables may override tile endpoints for a private/local tile
server without changing application code.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class MapLayer:
    id: str
    name: str
    kind: str
    url: str
    attribution: str
    enabled: bool = True
    max_zoom: int = 19
    notes: str = ""


OSM_TILES = os.getenv("RF_FINDER_OSM_TILES", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
USGS_IMAGERY = os.getenv(
    "RF_FINDER_USGS_IMAGERY_TILES",
    "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
)
USGS_TOPO = os.getenv(
    "RF_FINDER_USGS_TOPO_TILES",
    "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
)
USGS_RELIEF = os.getenv(
    "RF_FINDER_USGS_RELIEF_TILES",
    "https://basemap.nationalmap.gov/arcgis/rest/services/USGSShadedReliefOnly/MapServer/tile/{z}/{y}/{x}",
)
RF_FINDER_LOCAL_TILES = os.getenv("RF_FINDER_LOCAL_TILES", "http://127.0.0.1:8787/tiles/{z}/{x}/{y}.png")
RF_FINDER_DEM_TILES = os.getenv("RF_FINDER_DEM_TILES", "")


def default_layers() -> tuple[MapLayer, ...]:
    return (
        MapLayer("osm", "OpenStreetMap", "raster", OSM_TILES, "© OpenStreetMap contributors", True, 19),
        MapLayer("usgs-imagery", "USGS Satellite / Imagery", "raster", USGS_IMAGERY, "USGS", True, 19,
                  "Public-domain USGS National Map imagery; U.S. coverage."),
        MapLayer("usgs-topo", "USGS Topographic", "raster", USGS_TOPO, "USGS", True, 19),
        MapLayer("usgs-relief", "USGS Shaded Relief", "raster", USGS_RELIEF, "USGS", True, 19),
        MapLayer("local", "Local / Offline Tiles", "raster", RF_FINDER_LOCAL_TILES, "RF Finder local tiles", False, 22,
                  "Enable when a local tile service is running."),
    )


def map_layers_payload() -> dict[str, Any]:
    """Return a JSON-safe registry consumed by the MapLibre UI."""
    return {
        "engine": "maplibre-gl",
        "version": "6.9.0",
        "layers": [asdict(layer) for layer in default_layers()],
        "projection_modes": ["mercator", "globe"],
        "terrain": {
            "enabled": bool(RF_FINDER_DEM_TILES),
            "dem_tiles": RF_FINDER_DEM_TILES,
            "note": "3D terrain requires a configured raster-dem source; shaded relief is not a DEM.",
        },
        "google_earth": {
            "enabled": False,
            "reason": "Google Earth/Photorealistic 3D imagery requires a separately licensed Google service/API configuration.",
        },
        "rf_overlays": ["observations", "tracks", "heatmap", "investigations", "measurement_positions"],
    }


def validate_map_layer(layer: dict[str, Any]) -> None:
    """Validate a provider definition before it is accepted by a UI/config API."""
    required = ("id", "name", "kind", "url", "attribution")
    missing = [key for key in required if not str(layer.get(key, "")).strip()]
    if missing:
        raise ValueError(f"map layer missing required fields: {', '.join(missing)}")
    if layer["kind"] not in {"raster", "raster-dem", "vector"}:
        raise ValueError("unsupported map layer kind")
