from pathlib import Path
from collections import Counter
import json
from collections import defaultdict


raw_files = sorted(
    p for p in Path("data/raw").glob("osm_davao_transit_elements_*.json")
    if ".metadata." not in p.name
)

path = raw_files[-1]

with path.open("r", encoding="utf-8") as f:
    data = json.load(f)

elements = data["elements"]

print(f"File: {path}")
print(f"Total elements: {len(elements):,}")

print("\nELEMENT TYPES")
print(Counter(e.get("type") for e in elements))

tagged = [e for e in elements if e.get("tags")]
print(f"\nElements with tags: {len(tagged):,}")
print(f"Elements without tags: {len(elements) - len(tagged):,}")

route_relations = [
    e for e in elements
    if e.get("type") == "relation"
    and e.get("tags", {}).get("type") == "route"
]

print(f"\nRoute relations: {len(route_relations):,}")
print("Route modes:")
print(Counter(
    e.get("tags", {}).get("route", "<missing>")
    for e in route_relations
))

transit_stops = [
    e for e in elements
    if (
        "public_transport" in e.get("tags", {})
        or e.get("tags", {}).get("highway") == "bus_stop"
        or e.get("tags", {}).get("amenity")
        in {"bus_station", "ferry_terminal"}
    )
]

print(f"\nTransit stop candidates: {len(transit_stops):,}")

print("Public transport tags:")
print(Counter(
    e.get("tags", {}).get("public_transport", "<missing>")
    for e in transit_stops
))

missing_names = [
    e for e in transit_stops
    if not e.get("tags", {}).get("name")
]

print(
    f"Transit candidates missing name: "
    f"{len(missing_names):,}/{len(transit_stops):,}"
)

keys = [(e.get("type"), e.get("id")) for e in elements]

print(
    f"\nDuplicate (type, id) records: "
    f"{len(keys) - len(set(keys)):,}"
)

grouped = defaultdict(list)

for element in elements:
    key = (element.get("type"), element.get("id"))
    grouped[key].append(element)

duplicates = {
    key: records
    for key, records in grouped.items()
    if len(records) > 1
}

print("\n" + "=" * 60)
print("DUPLICATE ELEMENTS")
print("=" * 60)

for key, records in duplicates.items():
    print(f"\n{key} -> {len(records)} records")

    for i, record in enumerate(records, start=1):
        print(f"  Record {i}")
        print(f"    tags: {record.get('tags')}")
        print(f"    lat: {record.get('lat')}")
        print(f"    lon: {record.get('lon')}")

TRANSIT_MODES = {"bus", "ferry"}

transit_routes = [
    element
    for element in route_relations
    if element.get("tags", {}).get("route") in TRANSIT_MODES
]

print("\n" + "=" * 60)
print("PUBLIC TRANSIT ROUTES")
print("=" * 60)

for route in transit_routes:
    tags = route.get("tags", {})

    print(
        f"\nRelation {route['id']}"
        f"\n  mode: {tags.get('route')}"
        f"\n  ref: {tags.get('ref')}"
        f"\n  name: {tags.get('name')}"
        f"\n  from: {tags.get('from')}"
        f"\n  to: {tags.get('to')}"
        f"\n  operator: {tags.get('operator')}"
        f"\n  members: {len(route.get('members', []))}"
    )

member_roles = Counter()

for route in transit_routes:
    for member in route.get("members", []):
        role = member.get("role") or "<empty>"
        member_roles[role] += 1

print("\n" + "=" * 60)
print("TRANSIT ROUTE MEMBER ROLES")
print("=" * 60)

for role, count in member_roles.most_common():
    print(f"{role}: {count}")