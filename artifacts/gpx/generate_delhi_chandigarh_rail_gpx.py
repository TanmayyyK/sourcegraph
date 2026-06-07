#!/usr/bin/env python3
"""
Generate a railway-aligned, timestamped GPX track from Delhi Cantt to Chandigarh.

Rail geometry is pulled from OpenStreetMap railway ways. The moving track is snapped
to the rail centerline; the user-supplied approximate station coordinates are kept
in the station CSV for traceability.
"""

from __future__ import annotations

import csv
import heapq
import json
import math
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from xml.sax.saxutils import escape


OUT_DIR = Path(__file__).resolve().parent
GPX_PATH = OUT_DIR / "delhi_cantt_to_chandigarh_vande_bharat_rail.gpx"
POINTS_CSV_PATH = OUT_DIR / "delhi_cantt_to_chandigarh_vande_bharat_points.csv"
STATIONS_CSV_PATH = OUT_DIR / "delhi_cantt_to_chandigarh_station_order.csv"
MANIFEST_PATH = OUT_DIR / "delhi_cantt_to_chandigarh_vande_bharat_manifest.json"

RAIL_CACHE_PATH = Path("/tmp/delhi_chandigarh_overpass_rail.json")
STATION_CACHE_PATH = Path("/tmp/delhi_chandigarh_overpass_stations.json")

EARTH_RADIUS_M = 6_371_000
IST = timezone(timedelta(hours=5, minutes=30))
START_LOCAL = datetime(2026, 5, 14, 6, 0, 0, tzinfo=IST)
START_UTC = START_LOCAL.astimezone(timezone.utc)

BBOX = (28.50, 76.70, 30.76, 77.26)
MAX_INTERPOLATED_GAP_M = 650.0
CANDIDATES_PER_STATION = 60
STATION_OFFSET_PENALTY = 1.0


@dataclass(frozen=True)
class PrimaryStation:
    name: str
    provided_lat: float
    provided_lon: float
    anchor_lat: float
    anchor_lon: float
    stop_duration_s: int
    ref: str


PRIMARY_STATIONS: List[PrimaryStation] = [
    PrimaryStation("Delhi Cantt", 28.5883, 77.1405, 28.6117094, 77.1156635, 0, "DEC"),
    PrimaryStation("Subzi Mandi", 28.6729, 77.1988, 28.6685068, 77.2004935, 0, "SZM"),
    PrimaryStation("Badli", 28.7461, 77.1389, 28.7465404, 77.1374615, 0, "BHD"),
    PrimaryStation("Narela", 28.8515, 77.0920, 28.8464766, 77.0856631, 0, "NUR"),
    PrimaryStation("Sonipat Junction", 28.9931, 77.0151, 28.9898429, 77.0171182, 0, "SNP"),
    PrimaryStation("Ganaur", 29.1376, 77.0035, 29.1315256, 77.0110886, 0, "GNU"),
    PrimaryStation("Samalkha", 29.2355, 77.0120, 29.2415096, 77.0032892, 0, "SMK"),
    PrimaryStation("Panipat Junction", 29.3909, 76.9635, 29.3903294, 76.9640850, 45, "PNP"),
    PrimaryStation("Karnal", 29.6857, 76.9905, 29.6951152, 76.9698292, 30, "KUN"),
    PrimaryStation("Kurukshetra Junction", 29.9695, 76.8783, 29.9698587, 76.8517108, 20, "KKDE"),
    PrimaryStation("Shahbad Markanda", 30.1670, 76.8700, 30.1658852, 76.8616655, 0, "SHDM"),
    PrimaryStation("Ambala Cantt Junction", 30.3782, 76.7767, 30.3382427, 76.8286956, 90, "UMB"),
    PrimaryStation("Dappar", 30.5300, 76.8400, 30.5173904, 76.8073838, 0, "DHPR"),
    PrimaryStation("Ghagghar", 30.5965, 76.8170, 30.6102864, 76.8482707, 0, "GHG"),
    PrimaryStation("Chandigarh Junction", 30.7046, 76.8013, 30.7021622, 76.8214533, 0, "CDG"),
]

SEGMENT_MAX_SPEED_KMH = [
    45, 55, 80, 112, 120, 120, 115, 125, 125, 120, 115, 95, 85, 70
]


def overpass(query: str, cache_path: Path) -> dict:
    if cache_path.exists():
        return json.loads(cache_path.read_text())

    url = "https://overpass-api.de/api/interpreter"
    for attempt in range(4):
        try:
            try:
                import requests

                response = requests.get(
                    url,
                    params={"data": query},
                    headers={"User-Agent": "codex-railway-gpx-generator"},
                    timeout=240,
                )
                response.raise_for_status()
                payload = response.text
            except ImportError:
                request_url = url + "?" + urllib.parse.urlencode({"data": query})
                request = urllib.request.Request(request_url, headers={"User-Agent": "codex-railway-gpx-generator"})
                with urllib.request.urlopen(request, timeout=240) as response:
                    payload = response.read().decode("utf-8")
            cache_path.write_text(payload)
            return json.loads(payload)
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 + attempt * 2)
    raise RuntimeError("Overpass query failed")


def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def bearing_deg(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlambda = lon2 - lon1
    y = math.sin(dlambda) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def angle_delta_deg(a: float, b: float) -> float:
    return abs((b - a + 180) % 360 - 180)


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_graph(rail_data: dict) -> Tuple[Dict[int, Tuple[float, float]], Dict[int, List[Tuple[int, float]]]]:
    nodes = {
        element["id"]: (element["lat"], element["lon"])
        for element in rail_data["elements"]
        if element["type"] == "node"
    }
    graph: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    for element in rail_data["elements"]:
        if element["type"] != "way":
            continue
        if element.get("tags", {}).get("railway") != "rail":
            continue
        way_nodes = element.get("nodes", [])
        for left, right in zip(way_nodes, way_nodes[1:]):
            if left not in nodes or right not in nodes:
                continue
            distance = haversine_m(nodes[left], nodes[right])
            graph[left].append((right, distance))
            graph[right].append((left, distance))
    return nodes, graph


def dijkstra_all(graph: Dict[int, List[Tuple[int, float]]], source: int) -> Dict[int, float]:
    queue = [(0.0, source)]
    distances = {source: 0.0}
    seen = set()
    while queue:
        distance, node = heapq.heappop(queue)
        if node in seen:
            continue
        seen.add(node)
        for neighbor, edge_distance in graph[node]:
            new_distance = distance + edge_distance
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                heapq.heappush(queue, (new_distance, neighbor))
    return distances


def shortest_path(
    graph: Dict[int, List[Tuple[int, float]]],
    source: int,
    target: int,
) -> Tuple[float, List[int]]:
    queue = [(0.0, source)]
    distances = {source: 0.0}
    previous: Dict[int, int] = {}
    seen = set()
    while queue:
        distance, node = heapq.heappop(queue)
        if node in seen:
            continue
        if node == target:
            break
        seen.add(node)
        for neighbor, edge_distance in graph[node]:
            new_distance = distance + edge_distance
            if new_distance < distances.get(neighbor, float("inf")):
                distances[neighbor] = new_distance
                previous[neighbor] = node
                heapq.heappush(queue, (new_distance, neighbor))

    if target not in distances:
        raise RuntimeError(f"No rail path found between {source} and {target}")

    path = []
    cursor = target
    while cursor != source:
        path.append(cursor)
        cursor = previous[cursor]
    path.append(source)
    path.reverse()
    return distances[target], path


def nearest_candidates(
    nodes: Dict[int, Tuple[float, float]],
    coordinate: Tuple[float, float],
    count: int,
) -> List[Tuple[float, int]]:
    candidates = [(haversine_m(coordinate, node_coordinate), node_id) for node_id, node_coordinate in nodes.items()]
    candidates.sort()
    return candidates[:count]


def select_station_nodes(
    nodes: Dict[int, Tuple[float, float]],
    graph: Dict[int, List[Tuple[int, float]]],
) -> List[Tuple[float, int]]:
    candidates = [
        nearest_candidates(nodes, (station.anchor_lat, station.anchor_lon), CANDIDATES_PER_STATION)
        for station in PRIMARY_STATIONS
    ]

    transitions: List[List[List[float]]] = []
    for station_index in range(len(PRIMARY_STATIONS) - 1):
        segment_matrix: List[List[float]] = []
        for _, source_node in candidates[station_index]:
            distances = dijkstra_all(graph, source_node)
            segment_matrix.append([
                distances.get(target_node, float("inf"))
                for _, target_node in candidates[station_index + 1]
            ])
        transitions.append(segment_matrix)

    station_count = len(PRIMARY_STATIONS)
    candidate_count = CANDIDATES_PER_STATION
    dp = [[float("inf")] * candidate_count for _ in range(station_count)]
    previous_choice = [[-1] * candidate_count for _ in range(station_count)]

    for candidate_index, (offset, _) in enumerate(candidates[0]):
        dp[0][candidate_index] = STATION_OFFSET_PENALTY * offset

    for station_index in range(1, station_count):
        for candidate_index, (offset, _) in enumerate(candidates[station_index]):
            for previous_index in range(candidate_count):
                rail_distance = transitions[station_index - 1][previous_index][candidate_index]
                if not math.isfinite(rail_distance):
                    continue
                cost = dp[station_index - 1][previous_index] + rail_distance + STATION_OFFSET_PENALTY * offset
                if cost < dp[station_index][candidate_index]:
                    dp[station_index][candidate_index] = cost
                    previous_choice[station_index][candidate_index] = previous_index

    last_choice = min(range(candidate_count), key=lambda index: dp[-1][index])
    choices = [last_choice]
    for station_index in range(station_count - 1, 0, -1):
        choices.append(previous_choice[station_index][choices[-1]])
    choices.reverse()
    return [candidates[index][choice] for index, choice in enumerate(choices)]


def build_primary_route(
    nodes: Dict[int, Tuple[float, float]],
    graph: Dict[int, List[Tuple[int, float]]],
    selected_nodes: List[Tuple[float, int]],
) -> Tuple[List[dict], Dict[str, dict], List[dict]]:
    full_node_path: List[int] = []
    segment_summaries = []
    station_indexes = [0]

    for index in range(len(selected_nodes) - 1):
        source = selected_nodes[index][1]
        target = selected_nodes[index + 1][1]
        rail_distance, path = shortest_path(graph, source, target)
        segment_summaries.append({
            "from": PRIMARY_STATIONS[index].name,
            "to": PRIMARY_STATIONS[index + 1].name,
            "distance_km": rail_distance / 1000,
            "node_count": len(path),
        })
        if not full_node_path:
            full_node_path.extend(path)
        else:
            full_node_path.extend(path[1:])
        station_indexes.append(len(full_node_path) - 1)

    raw_points: List[dict] = []
    cumulative = 0.0
    for index, node_id in enumerate(full_node_path):
        lat, lon = nodes[node_id]
        if index:
            cumulative += haversine_m((raw_points[-1]["lat"], raw_points[-1]["lon"]), (lat, lon))
        raw_points.append({
            "lat": lat,
            "lon": lon,
            "cum_m": cumulative,
            "source": "osm_node",
            "node_id": node_id,
            "markers": [],
        })

    primary_markers: Dict[str, dict] = {}
    for order, (station, selected, route_index) in enumerate(zip(PRIMARY_STATIONS, selected_nodes, station_indexes), start=1):
        route_point = raw_points[route_index]
        marker = {
            "name": station.name,
            "order": order,
            "ref": station.ref,
            "kind": "primary",
            "stop_duration_s": station.stop_duration_s,
            "provided_lat": station.provided_lat,
            "provided_lon": station.provided_lon,
            "anchor_lat": station.anchor_lat,
            "anchor_lon": station.anchor_lon,
            "rail_lat": route_point["lat"],
            "rail_lon": route_point["lon"],
            "anchor_offset_m": selected[0],
            "provided_offset_m": haversine_m((station.provided_lat, station.provided_lon), (route_point["lat"], route_point["lon"])),
            "cum_m": route_point["cum_m"],
            "node_id": route_point["node_id"],
        }
        route_point["markers"].append(marker)
        primary_markers[normalize_name(station.name)] = marker

    return raw_points, primary_markers, segment_summaries


def recompute_cumulative(points: List[dict]) -> None:
    cumulative = 0.0
    for index, point in enumerate(points):
        if index:
            previous = points[index - 1]
            cumulative += haversine_m((previous["lat"], previous["lon"]), (point["lat"], point["lon"]))
        point["cum_m"] = cumulative
        for marker in point.get("markers", []):
            marker["cum_m"] = cumulative
            marker["rail_lat"] = point["lat"]
            marker["rail_lon"] = point["lon"]


def remove_short_spikes(points: List[dict]) -> List[dict]:
    cleaned = points[:]
    changed = True
    while changed:
        changed = False
        for index in range(1, len(cleaned) - 1):
            point = cleaned[index]
            if point.get("markers"):
                continue
            previous = cleaned[index - 1]
            following = cleaned[index + 1]
            previous_coord = (previous["lat"], previous["lon"])
            point_coord = (point["lat"], point["lon"])
            following_coord = (following["lat"], following["lon"])
            incoming = haversine_m(previous_coord, point_coord)
            outgoing = haversine_m(point_coord, following_coord)
            chord = haversine_m(previous_coord, following_coord)
            if incoming > 90 or outgoing > 90:
                continue
            angle = angle_delta_deg(bearing_deg(previous_coord, point_coord), bearing_deg(point_coord, following_coord))
            if angle > 145 and chord < 0.45 * (incoming + outgoing):
                del cleaned[index]
                changed = True
                break
    recompute_cumulative(cleaned)
    return cleaned


def point_segment_projection(
    point: Tuple[float, float],
    start: Tuple[float, float],
    end: Tuple[float, float],
) -> Tuple[float, Tuple[float, float], float]:
    lat0 = math.radians(point[0])
    meters_per_lat = 111_132.0
    meters_per_lon = 111_320.0 * math.cos(lat0)
    px = point[1] * meters_per_lon
    py = point[0] * meters_per_lat
    sx = start[1] * meters_per_lon
    sy = start[0] * meters_per_lat
    ex = end[1] * meters_per_lon
    ey = end[0] * meters_per_lat
    vx = ex - sx
    vy = ey - sy
    segment_length_sq = vx * vx + vy * vy
    if segment_length_sq == 0:
        t = 0.0
    else:
        t = max(0.0, min(1.0, ((px - sx) * vx + (py - sy) * vy) / segment_length_sq))
    projected_x = sx + t * vx
    projected_y = sy + t * vy
    projected = (projected_y / meters_per_lat, projected_x / meters_per_lon)
    offset = haversine_m(point, projected)
    return t, projected, offset


def nearest_route_projection(raw_points: List[dict], coordinate: Tuple[float, float]) -> Optional[dict]:
    best = None
    for index in range(len(raw_points) - 1):
        start = raw_points[index]
        end = raw_points[index + 1]
        segment_distance = end["cum_m"] - start["cum_m"]
        if segment_distance <= 0:
            continue
        t, projected, offset = point_segment_projection(
            coordinate,
            (start["lat"], start["lon"]),
            (end["lat"], end["lon"]),
        )
        candidate = {
            "segment_index": index,
            "t": t,
            "lat": projected[0],
            "lon": projected[1],
            "offset_m": offset,
            "cum_m": start["cum_m"] + t * segment_distance,
        }
        if best is None or candidate["offset_m"] < best["offset_m"]:
            best = candidate
    return best


def train_station_elements(station_data: dict) -> Iterable[dict]:
    for element in station_data["elements"]:
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:en")
        if not name:
            continue
        if tags.get("subway") == "yes" or tags.get("station") == "subway":
            continue
        if "metro" in tags.get("network", "").lower():
            continue
        if tags.get("train") == "no":
            continue
        if tags.get("railway") not in {"station", "halt"}:
            continue

        lat = element.get("lat")
        lon = element.get("lon")
        if lat is None or lon is None:
            center = element.get("center", {})
            lat = center.get("lat")
            lon = center.get("lon")
        if lat is None or lon is None:
            continue
        yield {
            "name": name,
            "ref": tags.get("ref", ""),
            "railway": tags.get("railway", ""),
            "lat": float(lat),
            "lon": float(lon),
            "osm_type": element.get("type"),
            "osm_id": element.get("id"),
        }


def collect_station_markers(
    raw_points: List[dict],
    primary_markers: Dict[str, dict],
    station_data: dict,
) -> List[dict]:
    markers = list(primary_markers.values())
    existing_by_name = dict(primary_markers)
    existing_primary_refs = {marker["ref"] for marker in primary_markers.values() if marker["ref"]}

    for station in train_station_elements(station_data):
        normalized = normalize_name(station["name"])
        if normalized in existing_by_name:
            continue
        if station["ref"] and station["ref"] in existing_primary_refs:
            continue
        projection = nearest_route_projection(raw_points, (station["lat"], station["lon"]))
        if not projection or projection["offset_m"] > 750:
            continue
        if any(abs(projection["cum_m"] - marker["cum_m"]) < 550 and normalize_name(marker["name"]) == normalized for marker in markers):
            continue

        marker = {
            "name": station["name"],
            "order": None,
            "ref": station["ref"],
            "kind": "intermediate",
            "stop_duration_s": 0,
            "provided_lat": "",
            "provided_lon": "",
            "anchor_lat": station["lat"],
            "anchor_lon": station["lon"],
            "rail_lat": projection["lat"],
            "rail_lon": projection["lon"],
            "anchor_offset_m": projection["offset_m"],
            "provided_offset_m": "",
            "cum_m": projection["cum_m"],
            "node_id": "",
        }
        markers.append(marker)
        existing_by_name[normalized] = marker

    markers.sort(key=lambda item: item["cum_m"])
    return markers


def interpolate_point(start: dict, end: dict, cum_m: float, marker: Optional[dict] = None) -> dict:
    segment_distance = end["cum_m"] - start["cum_m"]
    fraction = 0.0 if segment_distance <= 0 else (cum_m - start["cum_m"]) / segment_distance
    lat = start["lat"] + (end["lat"] - start["lat"]) * fraction
    lon = start["lon"] + (end["lon"] - start["lon"]) * fraction
    if marker:
        lat = marker["rail_lat"]
        lon = marker["rail_lon"]
    return {
        "lat": lat,
        "lon": lon,
        "cum_m": cum_m,
        "source": "station_projection" if marker else "interpolation",
        "node_id": "",
        "markers": [marker] if marker else [],
    }


def densify_route(raw_points: List[dict], markers: List[dict]) -> List[dict]:
    markers_by_cum = sorted(markers, key=lambda item: item["cum_m"])
    marker_index = 0
    dense_points = [raw_points[0].copy()]

    for index in range(len(raw_points) - 1):
        start = raw_points[index]
        end = raw_points[index + 1]
        internal: List[Tuple[float, Optional[dict]]] = []

        while marker_index < len(markers_by_cum) and markers_by_cum[marker_index]["cum_m"] <= start["cum_m"] + 0.5:
            if not dense_points[-1].get("markers"):
                dense_points[-1]["markers"] = []
            dense_points[-1]["markers"].append(markers_by_cum[marker_index])
            marker_index += 1

        lookahead = marker_index
        while lookahead < len(markers_by_cum) and markers_by_cum[lookahead]["cum_m"] < end["cum_m"] - 0.5:
            internal.append((markers_by_cum[lookahead]["cum_m"], markers_by_cum[lookahead]))
            lookahead += 1

        segment_distance = end["cum_m"] - start["cum_m"]
        if segment_distance > MAX_INTERPOLATED_GAP_M:
            steps = int(math.ceil(segment_distance / MAX_INTERPOLATED_GAP_M))
            for step in range(1, steps):
                internal.append((start["cum_m"] + segment_distance * step / steps, None))

        for cum_m, marker in sorted(internal, key=lambda item: item[0]):
            if dense_points and abs(dense_points[-1]["cum_m"] - cum_m) < 0.5:
                if marker:
                    dense_points[-1].setdefault("markers", []).append(marker)
                continue
            dense_points.append(interpolate_point(start, end, cum_m, marker))
            if marker:
                marker_index += 1

        dense_points.append(end.copy())

    while marker_index < len(markers_by_cum):
        marker = markers_by_cum[marker_index]
        if abs(dense_points[-1]["cum_m"] - marker["cum_m"]) < 0.5:
            dense_points[-1].setdefault("markers", []).append(marker)
        marker_index += 1

    deduped = [dense_points[0]]
    for point in dense_points[1:]:
        if haversine_m((deduped[-1]["lat"], deduped[-1]["lon"]), (point["lat"], point["lon"])) < 0.2:
            deduped[-1].setdefault("markers", []).extend(point.get("markers", []))
            continue
        deduped.append(point)
    return deduped


def assign_segments(points: List[dict], primary_markers: Dict[str, dict]) -> None:
    ordered_primary = sorted(primary_markers.values(), key=lambda item: item["cum_m"])
    for point in points:
        segment_index = 0
        while segment_index < len(ordered_primary) - 1 and point["cum_m"] > ordered_primary[segment_index + 1]["cum_m"]:
            segment_index += 1
        point["segment_index"] = min(segment_index, len(SEGMENT_MAX_SPEED_KMH) - 1)
        if segment_index < len(ordered_primary) - 1:
            point["segment_name"] = f"{ordered_primary[segment_index]['name']} → {ordered_primary[segment_index + 1]['name']}"
        else:
            point["segment_name"] = ordered_primary[-1]["name"]


def add_curve_metrics(points: List[dict]) -> None:
    for index, point in enumerate(points):
        point["curve_angle_deg"] = 0.0
        if index == 0 or index == len(points) - 1:
            continue
        prev_coord = (points[index - 1]["lat"], points[index - 1]["lon"])
        coord = (point["lat"], point["lon"])
        next_coord = (points[index + 1]["lat"], points[index + 1]["lon"])
        if haversine_m(prev_coord, coord) < 15 or haversine_m(coord, next_coord) < 15:
            continue
        point["curve_angle_deg"] = angle_delta_deg(bearing_deg(prev_coord, coord), bearing_deg(coord, next_coord))


def station_marker_at_point(point: dict) -> Optional[dict]:
    markers = point.get("markers", [])
    if not markers:
        return None
    primary = [marker for marker in markers if marker["kind"] == "primary"]
    return primary[0] if primary else markers[0]


def speed_caps_mps(points: List[dict], markers: List[dict]) -> List[float]:
    caps = []
    primary_stop_cums = {
        marker["cum_m"]: marker
        for marker in markers
        if marker["kind"] == "primary" and (marker["stop_duration_s"] > 0 or marker["name"] in {"Delhi Cantt", "Chandigarh Junction"})
    }

    station_cums = sorted(markers, key=lambda item: item["cum_m"])
    for point in points:
        segment_index = point["segment_index"]
        base = SEGMENT_MAX_SPEED_KMH[segment_index]
        cap = float(base)

        if segment_index <= 1:
            cap = min(cap, 55.0)
        if segment_index == 2:
            cap = min(cap, 82.0)
        if segment_index >= 11:
            cap = min(cap, 92.0)

        marker = station_marker_at_point(point)
        if marker and marker["kind"] == "primary" and (
            marker["stop_duration_s"] > 0 or marker["name"] in {"Delhi Cantt", "Chandigarh Junction"}
        ):
            caps.append(0.0)
            continue

        for station in station_cums:
            distance_to_station = abs(point["cum_m"] - station["cum_m"])
            if distance_to_station > 900:
                continue
            if station["kind"] == "primary" and station["stop_duration_s"] > 0:
                continue
            station_cap = 72.0
            if point["cum_m"] < 45_000 or station["name"] in {"Delhi Cantt", "Subzi Mandi", "Badli", "Narela"}:
                station_cap = 45.0 if distance_to_station < 350 else 60.0
            elif segment_index >= 11:
                station_cap = 58.0
            cap = min(cap, station_cap)

        for stop_cum, station in primary_stop_cums.items():
            distance = point["cum_m"] - stop_cum
            if station["name"] == "Chandigarh Junction" and abs(distance) < 1:
                cap = min(cap, 0.0)
            if distance >= 0:
                accel_distance = 7_000 if base >= 100 else 4_500
                if distance < accel_distance:
                    cap = min(cap, base * math.sqrt(max(distance, 0.0) / accel_distance))
            else:
                brake_distance = 7_000 if base >= 100 else 4_500
                if abs(distance) < brake_distance:
                    cap = min(cap, base * math.sqrt(abs(distance) / brake_distance))

        curve = point["curve_angle_deg"]
        if curve > 35:
            cap = min(cap, 35.0)
        elif curve > 22:
            cap = min(cap, 55.0)
        elif curve > 14:
            cap = min(cap, 78.0)

        caps.append(max(0.0, cap / 3.6))
    return caps


def smooth_speeds(points: List[dict], caps: List[float]) -> List[float]:
    speeds = caps[:]
    acceleration = 0.36
    braking = 0.48

    speeds[0] = 0.0
    for index in range(1, len(points)):
        distance = haversine_m(
            (points[index - 1]["lat"], points[index - 1]["lon"]),
            (points[index]["lat"], points[index]["lon"]),
        )
        reachable = math.sqrt(max(0.0, speeds[index - 1] ** 2 + 2 * acceleration * distance))
        speeds[index] = min(speeds[index], reachable)

    speeds[-1] = 0.0
    for index in range(len(points) - 2, -1, -1):
        distance = haversine_m(
            (points[index]["lat"], points[index]["lon"]),
            (points[index + 1]["lat"], points[index + 1]["lon"]),
        )
        reachable = math.sqrt(max(0.0, speeds[index + 1] ** 2 + 2 * braking * distance))
        speeds[index] = min(speeds[index], reachable)

    return speeds


def classify_waypoints(points: List[dict], markers: List[dict]) -> None:
    marker_cums = sorted(markers, key=lambda item: item["cum_m"])
    for index, point in enumerate(points):
        marker = station_marker_at_point(point)
        if marker:
            if marker["name"] == "Delhi Cantt":
                waypoint_type = "station_start"
            elif marker["name"] == "Chandigarh Junction":
                waypoint_type = "station_end"
            elif marker["stop_duration_s"] > 0:
                waypoint_type = "station_halt"
            elif marker["kind"] == "primary":
                waypoint_type = "station_pass_primary"
            else:
                waypoint_type = "intermediate_station_pass"
        else:
            nearest_marker = min(marker_cums, key=lambda item: abs(item["cum_m"] - point["cum_m"]))
            distance = point["cum_m"] - nearest_marker["cum_m"]
            if -1_000 <= distance < -30:
                waypoint_type = "station_approach"
            elif 30 < distance <= 1_000:
                waypoint_type = "station_exit"
            elif point["curve_angle_deg"] > 14:
                waypoint_type = "curve_apex"
            elif point["segment_index"] >= 11 and point["curve_angle_deg"] > 7:
                waypoint_type = "junction_deviation"
            elif point["source"] == "interpolation":
                waypoint_type = "interpolation"
            else:
                waypoint_type = "railway_geometry"
        point["waypoint_type"] = waypoint_type
        point["station_name"] = marker["name"] if marker else ""
        point["stop_duration_s"] = marker["stop_duration_s"] if marker else 0


def add_timestamps(points: List[dict], speeds_mps: List[float]) -> List[dict]:
    timed_points: List[dict] = []
    elapsed_seconds = 0.0

    for index, (point, speed_mps) in enumerate(zip(points, speeds_mps)):
        if index:
            previous = points[index - 1]
            distance = haversine_m((previous["lat"], previous["lon"]), (point["lat"], point["lon"]))
            average_speed = max(1.2, (speeds_mps[index - 1] + speed_mps) / 2)
            elapsed_seconds += distance / average_speed

        output_point = point.copy()
        output_point["speed_mps"] = speed_mps
        output_point["speed_kmh"] = speed_mps * 3.6
        output_point["time_utc"] = START_UTC + timedelta(seconds=elapsed_seconds)
        timed_points.append(output_point)

        if point["stop_duration_s"] > 0 and point["waypoint_type"] == "station_halt":
            elapsed_seconds += point["stop_duration_s"]
            dwell = output_point.copy()
            dwell["source"] = "station_dwell"
            dwell["waypoint_type"] = "station_halt_dwell"
            dwell["speed_mps"] = 0.0
            dwell["speed_kmh"] = 0.0
            dwell["time_utc"] = START_UTC + timedelta(seconds=elapsed_seconds)
            timed_points.append(dwell)

    return timed_points


def write_stations_csv(markers: List[dict]) -> None:
    fieldnames = [
        "route_order",
        "station_name",
        "station_kind",
        "ref",
        "provided_lat",
        "provided_lon",
        "rail_snapped_lat",
        "rail_snapped_lon",
        "provided_to_rail_offset_m",
        "anchor_to_rail_offset_m",
        "cumulative_km",
        "stop_duration_s",
        "osm_node_id",
    ]
    with STATIONS_CSV_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for order, marker in enumerate(sorted(markers, key=lambda item: item["cum_m"]), start=1):
            writer.writerow({
                "route_order": order,
                "station_name": marker["name"],
                "station_kind": marker["kind"],
                "ref": marker["ref"],
                "provided_lat": marker["provided_lat"],
                "provided_lon": marker["provided_lon"],
                "rail_snapped_lat": f"{marker['rail_lat']:.7f}",
                "rail_snapped_lon": f"{marker['rail_lon']:.7f}",
                "provided_to_rail_offset_m": "" if marker["provided_offset_m"] == "" else f"{marker['provided_offset_m']:.1f}",
                "anchor_to_rail_offset_m": f"{marker['anchor_offset_m']:.1f}",
                "cumulative_km": f"{marker['cum_m'] / 1000:.3f}",
                "stop_duration_s": marker["stop_duration_s"],
                "osm_node_id": marker["node_id"],
            })


def write_points_csv(timed_points: List[dict]) -> None:
    fieldnames = [
        "index",
        "time_utc",
        "latitude",
        "longitude",
        "cumulative_km",
        "waypoint_type",
        "station_name",
        "recommended_speed_kmh",
        "stop_duration_s",
        "segment_name",
        "curve_angle_deg",
        "source",
    ]
    with POINTS_CSV_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for index, point in enumerate(timed_points, start=1):
            writer.writerow({
                "index": index,
                "time_utc": xml_time(point["time_utc"]),
                "latitude": f"{point['lat']:.7f}",
                "longitude": f"{point['lon']:.7f}",
                "cumulative_km": f"{point['cum_m'] / 1000:.3f}",
                "waypoint_type": point["waypoint_type"],
                "station_name": point["station_name"],
                "recommended_speed_kmh": f"{point['speed_kmh']:.1f}",
                "stop_duration_s": point["stop_duration_s"],
                "segment_name": point["segment_name"],
                "curve_angle_deg": f"{point['curve_angle_deg']:.1f}",
                "source": point["source"],
            })


def xml_time(timestamp: datetime) -> str:
    return timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_gpx(timed_points: List[dict], markers: List[dict]) -> None:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="Codex railway GPX generator" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:sim="https://openai.com/codex/gpx-simulation" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.topografix.com/GPX/1/1 '
        'http://www.topografix.com/GPX/1/1/gpx.xsd">',
        "  <metadata>",
        "    <name>Delhi Cantt to Chandigarh Junction railway simulation</name>",
        "    <desc>Railway-aligned timed GPX generated from OpenStreetMap rail geometry with Vande Bharat style speed transitions.</desc>",
        f"    <time>{xml_time(START_UTC)}</time>",
        "  </metadata>",
    ]

    for marker in sorted(markers, key=lambda item: item["cum_m"]):
        lines.extend([
            f'  <wpt lat="{marker["rail_lat"]:.7f}" lon="{marker["rail_lon"]:.7f}">',
            f"    <name>{escape(marker['name'])}</name>",
            f"    <type>{escape(marker['kind'])}</type>",
            "    <extensions>",
            f"      <sim:ref>{escape(marker['ref'])}</sim:ref>",
            f"      <sim:cumulativeKm>{marker['cum_m'] / 1000:.3f}</sim:cumulativeKm>",
            f"      <sim:stopDurationSeconds>{marker['stop_duration_s']}</sim:stopDurationSeconds>",
            "    </extensions>",
            "  </wpt>",
        ])

    lines.extend([
        "  <trk>",
        "    <name>Delhi Cantt → Chandigarh Junction rail track</name>",
        "    <type>railway-simulation</type>",
        "    <trkseg>",
    ])

    for point in timed_points:
        lines.extend([
            f'      <trkpt lat="{point["lat"]:.7f}" lon="{point["lon"]:.7f}">',
            f"        <time>{xml_time(point['time_utc'])}</time>",
            "        <extensions>",
            f"          <sim:speedMps>{point['speed_mps']:.3f}</sim:speedMps>",
            f"          <sim:speedKmh>{point['speed_kmh']:.1f}</sim:speedKmh>",
            f"          <sim:cumulativeKm>{point['cum_m'] / 1000:.3f}</sim:cumulativeKm>",
            f"          <sim:waypointType>{escape(point['waypoint_type'])}</sim:waypointType>",
            f"          <sim:station>{escape(point['station_name'])}</sim:station>",
            f"          <sim:stopDurationSeconds>{point['stop_duration_s']}</sim:stopDurationSeconds>",
            "        </extensions>",
            "      </trkpt>",
        ])

    lines.extend([
        "    </trkseg>",
        "  </trk>",
        "</gpx>",
        "",
    ])
    GPX_PATH.write_text("\n".join(lines))


def write_manifest(timed_points: List[dict], markers: List[dict], segment_summaries: List[dict]) -> None:
    distances = [
        haversine_m((timed_points[index - 1]["lat"], timed_points[index - 1]["lon"]), (timed_points[index]["lat"], timed_points[index]["lon"]))
        for index in range(1, len(timed_points))
        if haversine_m((timed_points[index - 1]["lat"], timed_points[index - 1]["lon"]), (timed_points[index]["lat"], timed_points[index]["lon"])) > 0
    ]
    speeds = [point["speed_kmh"] for point in timed_points]
    moving_speeds = [speed for speed in speeds if speed > 0.1]
    total_seconds = (timed_points[-1]["time_utc"] - timed_points[0]["time_utc"]).total_seconds()
    manifest = {
        "source": "OpenStreetMap railway=rail geometry, Overpass API",
        "attribution": "© OpenStreetMap contributors; ODbL",
        "start_local": START_LOCAL.isoformat(),
        "start_utc": xml_time(START_UTC),
        "end_utc": xml_time(timed_points[-1]["time_utc"]),
        "duration_seconds": total_seconds,
        "duration_hms": str(timedelta(seconds=int(total_seconds))),
        "total_distance_km": timed_points[-1]["cum_m"] / 1000,
        "trackpoint_count": len(timed_points),
        "station_marker_count": len(markers),
        "max_segment_gap_m": max(distances),
        "mean_segment_gap_m": sum(distances) / len(distances),
        "max_speed_kmh": max(speeds),
        "mean_moving_speed_kmh": sum(moving_speeds) / len(moving_speeds),
        "stop_durations": {
            marker["name"]: marker["stop_duration_s"]
            for marker in markers
            if marker["stop_duration_s"] > 0
        },
        "primary_segments": segment_summaries,
        "outputs": {
            "gpx": str(GPX_PATH),
            "points_csv": str(POINTS_CSV_PATH),
            "stations_csv": str(STATIONS_CSV_PATH),
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))


def main() -> None:
    south, west, north, east = BBOX
    rail_query = f"""
[out:json][timeout:240];
way["railway"="rail"]({south},{west},{north},{east});
out body;
>;
out skel qt;
"""
    station_query = f"""
[out:json][timeout:180];
(
  node["railway"~"^(station|halt)$"]({south},{west},{north},{east});
  way["railway"~"^(station|halt)$"]({south},{west},{north},{east});
  relation["railway"~"^(station|halt)$"]({south},{west},{north},{east});
);
out center tags;
"""

    rail_data = overpass(rail_query, RAIL_CACHE_PATH)
    station_data = overpass(station_query, STATION_CACHE_PATH)
    nodes, graph = build_graph(rail_data)

    selected_nodes = select_station_nodes(nodes, graph)
    raw_points, primary_markers, segment_summaries = build_primary_route(nodes, graph, selected_nodes)
    raw_points = remove_short_spikes(raw_points)
    markers = collect_station_markers(raw_points, primary_markers, station_data)
    dense_points = densify_route(raw_points, markers)
    assign_segments(dense_points, primary_markers)
    add_curve_metrics(dense_points)
    caps = speed_caps_mps(dense_points, markers)
    speeds = smooth_speeds(dense_points, caps)
    classify_waypoints(dense_points, markers)
    timed_points = add_timestamps(dense_points, speeds)

    write_stations_csv(markers)
    write_points_csv(timed_points)
    write_gpx(timed_points, markers)
    write_manifest(timed_points, markers, segment_summaries)

    print(json.dumps({
        "gpx": str(GPX_PATH),
        "points_csv": str(POINTS_CSV_PATH),
        "stations_csv": str(STATIONS_CSV_PATH),
        "manifest": str(MANIFEST_PATH),
        "trackpoints": len(timed_points),
        "distance_km": round(timed_points[-1]["cum_m"] / 1000, 3),
        "duration": str(timed_points[-1]["time_utc"] - timed_points[0]["time_utc"]),
    }, indent=2))


if __name__ == "__main__":
    main()
