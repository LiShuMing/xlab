import json
from collections import defaultdict

def normalize_positions(stations):
    """
    Normalize lon/lat to x/y in [0, 1].
    y is flipped (north = smaller y) for screen-friendly coordinates.
    """
    xs = [s["lon"] for s in stations.values()]
    ys = [s["lat"] for s in stations.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    def nx(v):  # lon -> x
        return 0.5 if max_x == min_x else (v - min_x) / (max_x - min_x)

    def ny(v):  # lat -> y (flip)
        if max_y == min_y:
            return 0.5
        return 1.0 - (v - min_y) / (max_y - min_y)

    for st in stations.values():
        st["x"] = nx(st["lon"])
        st["y"] = ny(st["lat"])

def main(in_path: str, out_path: str):
    raw = json.load(open(in_path, "r", encoding="utf-8"))

    # Amap subway schema (commonly):
    # raw["l"] -> list of lines
    # line["ln"] line name, line["st"] station list
    # station["n"] name, station["sl"] "lon,lat"
    lines = raw.get("l", [])
    if not lines:
        raise RuntimeError("Unexpected input: missing top-level 'l' (lines).")

    stations = {}  # name -> station dict
    station_lines = defaultdict(list)  # name -> [{line, order}, ...]

    line_stations = {}  # line_name -> [station_name in order]
    # Some cities have duplicate station names in different places (rare in BJ but possible).
    # If you want uniqueness beyond name, you can key by (name, lon, lat) instead.
    for line in lines:
        line_name = line.get("ln") or line.get("name") or line.get("ls") or "UNKNOWN_LINE"
        st_list = line.get("st", [])

        ordered_names = []
        for idx, st in enumerate(st_list, start=1):
            name = st.get("n") or st.get("name")
            sl = st.get("sl") or st.get("lonlat") or ""
            if not name or "," not in sl:
                # Skip malformed entries
                continue
            lon_s, lat_s = sl.split(",", 1)
            lon = float(lon_s)
            lat = float(lat_s)

            if name not in stations:
                stations[name] = {
                    "name": name,
                    "lon": lon,
                    "lat": lat,
                    "lines": []
                }

            station_lines[name].append({"line": line_name, "order": idx})
            ordered_names.append(name)

        if ordered_names:
            line_stations[line_name] = ordered_names

    # attach line membership
    for name, memberships in station_lines.items():
        # keep stable ordering: by line name then station order
        memberships.sort(key=lambda x: (x["line"], x["order"]))
        stations[name]["lines"] = memberships

    # compute x/y
    normalize_positions(stations)

    out = {
        "meta": {
            "source": "Amap subway JSON (Beijing 1100_drw_beijing.json)",
            "coord_system": "x,y normalized from lon/lat to [0,1]",
            "note": "These are geographic-relative positions, not the schematic metro-map layout."
        },
        "lines": line_stations,
        "stations": stations
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK: wrote {out_path}")
    print(f"lines={len(out['lines'])}, stations={len(out['stations'])}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python gen_bj_subway_layout.py <beijing_amap_subway.json> <out.json>")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
