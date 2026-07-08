from datetime import datetime, timezone
from pathlib import Path
import json
import requests


RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Davao City OSM relation: 3936841
# Overpass area ID convention: 3600000000 + relation_id
DAVAO_CITY_AREA_ID = 3603936841

QUERY = f"""
[out:json][timeout:120];

area({DAVAO_CITY_AREA_ID})->.davao;

(
  node["public_transport"](area.davao);
  node["highway"="bus_stop"](area.davao);
  node["amenity"~"bus_station|ferry_terminal"](area.davao);
  way["public_transport"](area.davao);
  relation["type"="route"](area.davao);
);

out body geom;
>;
out skel qt;
"""


def fetch_overpass_data(query: str) -> dict:
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": "dep-data-engineering-vn0raven/0.1"},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def save_raw_json(data: dict, output_path: Path) -> None:
    output_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main() -> None:
    pull_date = datetime.now(timezone.utc).strftime("%Y%m%d")
    output_file = RAW_DIR / f"osm_davao_transit_elements_{pull_date}.json"

    print("Pulling Davao City transit-related OSM data from Overpass API...")
    data = fetch_overpass_data(QUERY)

    save_raw_json(data, output_file)

    element_count = len(data.get("elements", []))
    print(f"Saved {element_count:,} OSM elements to {output_file}")


if __name__ == "__main__":
    main()
