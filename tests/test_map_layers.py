from app.map_layers import default_layers, map_layers_payload, validate_map_layer


def test_default_map_layers_include_free_basemaps_and_local_override():
    layers = {layer.id: layer for layer in default_layers()}
    assert {"osm", "usgs-imagery", "usgs-topo", "usgs-relief", "local"}.issubset(layers)
    assert layers["osm"].url.startswith("https://tile.openstreetmap.org/")
    assert layers["local"].enabled is False


def test_map_payload_separates_google_earth_from_enabled_providers():
    payload = map_layers_payload()
    assert payload["engine"] == "maplibre-gl"
    assert "globe" in payload["projection_modes"]
    assert payload["google_earth"]["enabled"] is False
    assert "observations" in payload["rf_overlays"]


def test_map_layer_validation_rejects_unknown_kind():
    try:
        validate_map_layer({"id": "x", "name": "X", "kind": "bogus", "url": "x", "attribution": "x"})
    except ValueError as exc:
        assert "unsupported map layer kind" in str(exc)
    else:
        raise AssertionError("expected validation failure")
