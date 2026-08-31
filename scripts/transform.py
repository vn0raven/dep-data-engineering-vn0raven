"""
Transform raw Davao City OpenStreetMap transit data into clean,
structured datasets for analysis.

Outputs:
    data/processed/stops.csv
    data/processed/routes.csv
    data/processed/route_stops.csv
    data/processed/processing_summary.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


TRANSIT_MODES = {
    "bus",
    "ferry",
}

STOP_MEMBER_ROLES = {
    "stop",
    "stop_entry_only",
    "stop_exit_only",
    "platform",
    "platform_entry_only",
    "platform_exit_only",
}

STOP_COLUMNS = [
    "stop_id",
    "osm_type",
    "osm_id",
    "name",
    "stop_type",
    "latitude",
    "longitude",
    "public_transport",
    "highway",
    "amenity",
    "bus",
    "ferry",
    "evidence",
    "route_member_roles",
    "source_file",
]

ROUTE_COLUMNS = [
    "route_id",
    "osm_relation_id",
    "route_ref",
    "route_name",
    "route_mode",
    "operator",
    "network",
    "origin_name",
    "destination_name",
    "source_file",
]

ROUTE_STOP_COLUMNS = [
    "route_id",
    "stop_sequence",
    "member_index",
    "stop_id",
    "member_osm_type",
    "member_osm_id",
    "member_role",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transform raw OSM transit data into processed datasets."
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to raw OSM JSON file.",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory for processed outputs.",
    )

    return parser.parse_args()


def load_raw(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Raw input file does not exist: {path}")

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    elements = payload.get("elements")

    if not isinstance(elements, list):
        raise ValueError("Raw OSM file does not contain an 'elements' list.")

    return elements


def element_key(element: dict[str, Any]) -> tuple[str, int]:
    return element["type"], int(element["id"])


def record_quality(element: dict[str, Any]) -> tuple[int, int, int, int]:
    """
    Rank duplicate OSM records deterministically.

    Tagged and geometrically richer records are preferred over
    untagged supporting records produced by the Overpass query.
    """

    tags = element.get("tags") or {}
    geometry = element.get("geometry") or []
    members = element.get("members") or []

    has_coordinates = int(
        element.get("lat") is not None
        and element.get("lon") is not None
    )

    return (
        len(tags),
        has_coordinates,
        len(geometry),
        len(members),
    )


def deduplicate_elements(
    elements: list[dict[str, Any]],
) -> tuple[dict[tuple[str, int], dict[str, Any]], int]:

    selected: dict[tuple[str, int], dict[str, Any]] = {}

    for element in elements:
        if "type" not in element or "id" not in element:
            continue

        key = element_key(element)

        existing = selected.get(key)

        if existing is None:
            selected[key] = element
            continue

        if record_quality(element) > record_quality(existing):
            selected[key] = element

    duplicates_removed = len(elements) - len(selected)

    return selected, duplicates_removed


def is_transit_route(element: dict[str, Any]) -> bool:
    if element.get("type") != "relation":
        return False

    tags = element.get("tags") or {}

    return (
        tags.get("type") == "route"
        and tags.get("route") in TRANSIT_MODES
    )


def is_tagged_transit_stop(element: dict[str, Any]) -> bool:
    tags = element.get("tags") or {}

    public_transport = tags.get("public_transport")
    highway = tags.get("highway")
    amenity = tags.get("amenity")

    return (
        public_transport in {
            "platform",
            "station",
            "stop_position",
        }
        or highway == "bus_stop"
        or amenity in {
            "bus_station",
            "ferry_terminal",
        }
    )


def representative_coordinates(
    element: dict[str, Any],
) -> tuple[float | None, float | None]:

    lat = element.get("lat")
    lon = element.get("lon")

    if lat is not None and lon is not None:
        return float(lat), float(lon)

    center = element.get("center") or {}

    if center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])

    geometry = element.get("geometry") or []

    points = [
        (point["lat"], point["lon"])
        for point in geometry
        if point.get("lat") is not None
        and point.get("lon") is not None
    ]

    if points:
        latitude = sum(point[0] for point in points) / len(points)
        longitude = sum(point[1] for point in points) / len(points)

        return float(latitude), float(longitude)

    return None, None


def derive_stop_type(
    tags: dict[str, Any],
    roles: set[str],
) -> str:

    public_transport = tags.get("public_transport")

    if public_transport:
        return str(public_transport)

    if tags.get("highway") == "bus_stop":
        return "bus_stop"

    if tags.get("amenity") == "bus_station":
        return "bus_station"

    if tags.get("amenity") == "ferry_terminal":
        return "ferry_terminal"

    if any(role.startswith("platform") for role in roles):
        return "platform"

    if any(role.startswith("stop") for role in roles):
        return "stop_position"

    return "unknown"


def build_routes(
    transit_routes: list[dict[str, Any]],
    source_file: str,
) -> pd.DataFrame:

    rows = []

    for route in transit_routes:
        tags = route.get("tags") or {}

        rows.append(
            {
                "route_id": f"relation:{route['id']}",
                "osm_relation_id": int(route["id"]),
                "route_ref": tags.get("ref"),
                "route_name": tags.get("name"),
                "route_mode": tags.get("route"),
                "operator": tags.get("operator"),
                "network": tags.get("network"),
                "origin_name": tags.get("from"),
                "destination_name": tags.get("to"),
                "source_file": source_file,
            }
        )

    dataframe = pd.DataFrame(rows, columns=ROUTE_COLUMNS)

    return dataframe.sort_values(
        by=["osm_relation_id"],
        kind="stable",
    ).reset_index(drop=True)


def collect_route_stop_references(
    transit_routes: list[dict[str, Any]],
) -> tuple[
    set[tuple[str, int]],
    dict[tuple[str, int], set[str]],
    dict[tuple[str, int], dict[str, Any]],
]:

    referenced_keys: set[tuple[str, int]] = set()
    roles_by_key: dict[tuple[str, int], set[str]] = defaultdict(set)
    member_payloads: dict[tuple[str, int], dict[str, Any]] = {}

    for route in transit_routes:
        for member in route.get("members") or []:
            role = member.get("role") or ""

            if role not in STOP_MEMBER_ROLES:
                continue

            if "type" not in member or "ref" not in member:
                continue

            key = (
                member["type"],
                int(member["ref"]),
            )

            referenced_keys.add(key)
            roles_by_key[key].add(role)

            if key not in member_payloads:
                member_payloads[key] = member

    return referenced_keys, roles_by_key, member_payloads


def build_stops(
    element_lookup: dict[tuple[str, int], dict[str, Any]],
    transit_routes: list[dict[str, Any]],
    source_file: str,
) -> pd.DataFrame:

    tagged_stop_keys = {
        key
        for key, element in element_lookup.items()
        if is_tagged_transit_stop(element)
    }

    (
        route_stop_keys,
        roles_by_key,
        member_payloads,
    ) = collect_route_stop_references(transit_routes)

    all_stop_keys = tagged_stop_keys | route_stop_keys

    rows = []

    for osm_type, osm_id in sorted(all_stop_keys):
        key = (osm_type, osm_id)

        element = element_lookup.get(key)

        if element is None:
            element = member_payloads.get(key, {})

        tags = element.get("tags") or {}
        roles = roles_by_key.get(key, set())

        latitude, longitude = representative_coordinates(element)

        if key in tagged_stop_keys and key in route_stop_keys:
            evidence = "tagged+route_member"
        elif key in tagged_stop_keys:
            evidence = "tagged"
        else:
            evidence = "route_member"

        rows.append(
            {
                "stop_id": f"{osm_type}:{osm_id}",
                "osm_type": osm_type,
                "osm_id": osm_id,
                "name": tags.get("name"),
                "stop_type": derive_stop_type(tags, roles),
                "latitude": latitude,
                "longitude": longitude,
                "public_transport": tags.get("public_transport"),
                "highway": tags.get("highway"),
                "amenity": tags.get("amenity"),
                "bus": tags.get("bus"),
                "ferry": tags.get("ferry"),
                "evidence": evidence,
                "route_member_roles": ",".join(sorted(roles)) or None,
                "source_file": source_file,
            }
        )

    dataframe = pd.DataFrame(rows, columns=STOP_COLUMNS)

    return dataframe.sort_values(
        by=["osm_type", "osm_id"],
        kind="stable",
    ).reset_index(drop=True)


def build_route_stops(
    transit_routes: list[dict[str, Any]],
) -> pd.DataFrame:

    rows = []

    for route in sorted(
        transit_routes,
        key=lambda item: int(item["id"]),
    ):
        route_id = f"relation:{route['id']}"

        stop_sequence = 0

        for member_index, member in enumerate(
            route.get("members") or [],
            start=1,
        ):
            role = member.get("role") or ""

            if role not in STOP_MEMBER_ROLES:
                continue

            if "type" not in member or "ref" not in member:
                continue

            stop_sequence += 1

            member_type = member["type"]
            member_id = int(member["ref"])

            rows.append(
                {
                    "route_id": route_id,
                    "stop_sequence": stop_sequence,
                    "member_index": member_index,
                    "stop_id": f"{member_type}:{member_id}",
                    "member_osm_type": member_type,
                    "member_osm_id": member_id,
                    "member_role": role,
                }
            )

    dataframe = pd.DataFrame(
        rows,
        columns=ROUTE_STOP_COLUMNS,
    )

    return dataframe.sort_values(
        by=["route_id", "stop_sequence"],
        kind="stable",
    ).reset_index(drop=True)


def validate(
    stops: pd.DataFrame,
    routes: pd.DataFrame,
    route_stops: pd.DataFrame,
) -> None:

    if stops.empty:
        raise ValueError("Validation failed: stops dataset is empty.")

    if routes.empty:
        raise ValueError("Validation failed: routes dataset is empty.")

    if route_stops.empty:
        raise ValueError(
            "Validation failed: route_stops dataset is empty."
        )

    if stops["stop_id"].isna().any():
        raise ValueError("Validation failed: null stop_id found.")

    if stops["stop_id"].duplicated().any():
        raise ValueError("Validation failed: duplicate stop_id found.")

    if routes["route_id"].isna().any():
        raise ValueError("Validation failed: null route_id found.")

    if routes["route_id"].duplicated().any():
        raise ValueError("Validation failed: duplicate route_id found.")

    if routes["osm_relation_id"].duplicated().any():
        raise ValueError(
            "Validation failed: duplicate OSM relation ID found."
        )

    if route_stops[
        ["route_id", "stop_sequence"]
    ].duplicated().any():
        raise ValueError(
            "Validation failed: duplicate "
            "(route_id, stop_sequence) found."
        )

    if (route_stops["stop_sequence"] < 1).any():
        raise ValueError(
            "Validation failed: invalid stop sequence found."
        )

    missing_lat = stops["latitude"].isna()
    missing_lon = stops["longitude"].isna()

    if not missing_lat.equals(missing_lon):
        raise ValueError(
            "Validation failed: stop has only one coordinate."
        )

    known_coordinates = stops[
        stops["latitude"].notna()
        & stops["longitude"].notna()
    ]

    if not known_coordinates["latitude"].between(-90, 90).all():
        raise ValueError(
            "Validation failed: invalid latitude found."
        )

    if not known_coordinates["longitude"].between(-180, 180).all():
        raise ValueError(
            "Validation failed: invalid longitude found."
        )

    route_ids = set(routes["route_id"])
    route_stop_route_ids = set(route_stops["route_id"])

    if not route_stop_route_ids.issubset(route_ids):
        raise ValueError(
            "Validation failed: route_stops contains unknown route_id."
        )

    stop_ids = set(stops["stop_id"])
    route_stop_stop_ids = set(route_stops["stop_id"])

    if not route_stop_stop_ids.issubset(stop_ids):
        raise ValueError(
            "Validation failed: route_stops contains unknown stop_id."
        )


def write_csv(
    dataframe: pd.DataFrame,
    path: Path,
) -> None:

    dataframe.to_csv(
        path,
        index=False,
        encoding="utf-8",
        lineterminator="\n",
        na_rep="",
        float_format="%.7f",
    )


def main() -> None:
    args = parse_args()

    input_path = args.input
    output_dir = args.output_dir

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    elements = load_raw(input_path)

    element_lookup, duplicates_removed = deduplicate_elements(
        elements
    )

    transit_routes = [
        element
        for element in element_lookup.values()
        if is_transit_route(element)
    ]

    transit_routes = sorted(
        transit_routes,
        key=lambda element: int(element["id"]),
    )

    stops = build_stops(
        element_lookup,
        transit_routes,
        input_path.name,
    )

    routes = build_routes(
        transit_routes,
        input_path.name,
    )

    route_stops = build_route_stops(
        transit_routes,
    )

    validate(
        stops,
        routes,
        route_stops,
    )

    write_csv(
        stops,
        output_dir / "stops.csv",
    )

    write_csv(
        routes,
        output_dir / "routes.csv",
    )

    write_csv(
        route_stops,
        output_dir / "route_stops.csv",
    )

    all_route_modes = Counter()

    for element in element_lookup.values():
        if element.get("type") != "relation":
            continue

        tags = element.get("tags") or {}

        if tags.get("type") == "route":
            all_route_modes[
                tags.get("route") or "<missing>"
            ] += 1

    summary = {
        "source_file": input_path.name,
        "raw_element_count": len(elements),
        "unique_element_count": len(element_lookup),
        "duplicate_records_removed": duplicates_removed,
        "processed_stop_count": len(stops),
        "processed_route_count": len(routes),
        "route_stop_occurrence_count": len(route_stops),
        "unnamed_stop_count": int(stops["name"].isna().sum()),
        "stops_without_coordinates": int(
            stops["latitude"].isna().sum()
        ),
        "route_modes_observed": dict(
            sorted(all_route_modes.items())
        ),
        "processed_route_modes": sorted(TRANSIT_MODES),
        "cleaning_decisions": {
            "duplicates": (
                "Keep the richest record for each "
                "(OSM type, OSM ID)."
            ),
            "routes": (
                "Retain route relations whose route mode is "
                "bus or ferry."
            ),
            "stops": (
                "Retain tagged transit stops plus objects "
                "explicitly referenced using stop/platform "
                "route-member roles."
            ),
            "missing_names": (
                "Preserve valid unnamed stops as null."
            ),
            "missing_route_metadata": (
                "Do not infer missing ref, operator, from, or to values."
            ),
            "route_geometry": (
                "Unlabelled route relation members are treated "
                "as geometry, not stops."
            ),
        },
    }

    summary_path = output_dir / "processing_summary.json"

    with summary_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as file:
        json.dump(
            summary,
            file,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )

        file.write("\n")

    print("Transformation complete.")
    print(f"Source: {input_path}")
    print(f"Raw elements: {len(elements):,}")
    print(f"Duplicates removed: {duplicates_removed:,}")
    print(f"Stops: {len(stops):,}")
    print(f"Routes: {len(routes):,}")
    print(f"Route-stop occurrences: {len(route_stops):,}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()