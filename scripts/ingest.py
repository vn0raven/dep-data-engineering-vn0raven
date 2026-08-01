"""Download raw Davao City public-transport data from the Overpass API.

Each successful run writes two timestamped files to ``data/raw``:

1. the unmodified JSON response returned by Overpass; and
2. a metadata sidecar recording the source URL, access time, query, checksum,
   response size, and element count.

Run from any working directory with:
    python scripts/ingest.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SCRIPT_VERSION = "2.0.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"
SOURCE_LANDING_PAGE = "https://overpass-api.de/"
DEFAULT_USER_AGENT = (
    "dep-data-engineering-vn0raven/2.0 "
    "(https://github.com/vn0raven/dep-data-engineering-vn0raven)"
)

# Davao City OSM relation: 3936841.
# Overpass area IDs for OSM relations use 3,600,000,000 + relation ID.
DAVAO_CITY_RELATION_ID = 3_936_841
DAVAO_CITY_AREA_ID = 3_603_936_841

QUERY_NAME = "davao_transit_elements"
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
""".strip()

RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


class IngestionError(RuntimeError):
    """Raised when the source cannot be fetched or validated."""


@dataclass(frozen=True)
class FetchResult:
    """Validated response data needed by the save step."""

    content: bytes
    payload: dict[str, Any]
    status_code: int
    content_type: str
    elapsed_seconds: float
    accessed_at_utc: datetime


def utc_timestamp(value: datetime) -> str:
    """Return a compact UTC timestamp suitable for filenames."""

    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def isoformat_utc(value: datetime) -> str:
    """Return an ISO 8601 UTC timestamp ending in Z."""

    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def sha256_bytes(content: bytes) -> str:
    """Calculate the SHA-256 checksum of bytes."""

    return hashlib.sha256(content).hexdigest()


def build_session(retries: int, backoff_factor: float) -> requests.Session:
    """Create an HTTP session that retries transient API failures."""

    retry_policy = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRYABLE_STATUS_CODES,
        allowed_methods=frozenset({"POST"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_policy)

    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_overpass_data(
    *,
    session: requests.Session,
    endpoint: str,
    query: str,
    timeout_seconds: int,
    user_agent: str,
) -> FetchResult:
    """POST an Overpass QL query and validate the JSON response."""

    try:
        response = session.post(
            endpoint,
            data={"data": query},
            headers={
                "Accept": "application/json",
                "User-Agent": user_agent,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise IngestionError(f"Overpass request failed: {exc}") from exc

    try:
        payload = response.json()
    except requests.exceptions.JSONDecodeError as exc:
        preview = response.text[:200].replace("\n", " ")
        raise IngestionError(
            "Overpass returned a non-JSON response. "
            f"Content-Type={response.headers.get('Content-Type', 'unknown')!r}; "
            f"preview={preview!r}"
        ) from exc

    if not isinstance(payload, dict):
        raise IngestionError("Overpass JSON response must be an object.")

    elements = payload.get("elements")
    if not isinstance(elements, list):
        remark = payload.get("remark")
        detail = f" Server remark: {remark}" if remark else ""
        raise IngestionError(
            "Overpass response does not contain an 'elements' list." + detail
        )

    return FetchResult(
        content=response.content,
        payload=payload,
        status_code=response.status_code,
        content_type=response.headers.get("Content-Type", ""),
        elapsed_seconds=response.elapsed.total_seconds(),
        accessed_at_utc=datetime.now(timezone.utc),
    )


def atomic_write_bytes(path: Path, content: bytes) -> None:
    """Write bytes atomically so failed runs do not leave partial raw files."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(content)
    temporary_path.replace(path)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write formatted JSON atomically."""

    encoded = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write_bytes(path, encoded)


def build_metadata(
    *,
    raw_path: Path,
    result: FetchResult,
    endpoint: str,
    query: str,
    timeout_seconds: int,
    retries: int,
    user_agent: str,
) -> dict[str, Any]:
    """Create the source and lineage record stored beside each raw extract."""

    return {
        "dataset_name": "OpenStreetMap Davao City transit elements",
        "raw_file": raw_path.name,
        "ingestion_method": "API",
        "source_name": "OpenStreetMap data via Overpass API",
        "source_url": endpoint,
        "source_landing_page": SOURCE_LANDING_PAGE,
        "accessed_at_utc": isoformat_utc(result.accessed_at_utc),
        "query_name": QUERY_NAME,
        "query_language": "Overpass QL",
        "query": query,
        "geographic_scope": {
            "name": "Davao City, Philippines",
            "osm_relation_id": DAVAO_CITY_RELATION_ID,
            "overpass_area_id": DAVAO_CITY_AREA_ID,
        },
        "request": {
            "method": "POST",
            "timeout_seconds": timeout_seconds,
            "configured_retries": retries,
            "user_agent": user_agent,
        },
        "response": {
            "status_code": result.status_code,
            "content_type": result.content_type,
            "elapsed_seconds": round(result.elapsed_seconds, 3),
            "byte_count": len(result.content),
            "element_count": len(result.payload["elements"]),
            "sha256": sha256_bytes(result.content),
        },
        "producer": {
            "script": "scripts/ingest.py",
            "script_version": SCRIPT_VERSION,
        },
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""

    parser = argparse.ArgumentParser(
        description=(
            "Fetch Davao City transit-related OpenStreetMap data from the "
            "Overpass API and save a timestamped raw JSON file plus metadata."
        )
    )
    parser.add_argument(
        "--endpoint",
        default=DEFAULT_ENDPOINT,
        help=f"Overpass interpreter URL (default: {DEFAULT_ENDPOINT})",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help=f"Output directory (default: {DEFAULT_RAW_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="HTTP timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=4,
        help="Retries for transient HTTP failures (default: 4)",
    )
    parser.add_argument(
        "--backoff",
        type=float,
        default=2.0,
        help="Exponential retry backoff factor (default: 2.0)",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent sent to Overpass",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the source URL and query without calling the API",
    )
    return parser.parse_args(argv)


def validate_args(args: argparse.Namespace) -> None:
    """Reject invalid numeric options before making a request."""

    if args.timeout <= 0:
        raise IngestionError("--timeout must be greater than zero.")
    if args.retries < 0:
        raise IngestionError("--retries cannot be negative.")
    if args.backoff < 0:
        raise IngestionError("--backoff cannot be negative.")


def main(argv: list[str] | None = None) -> int:
    """Run the ingestion process and return a process exit code."""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)

    try:
        validate_args(args)

        if args.dry_run:
            print(f"Source URL: {args.endpoint}")
            print(QUERY)
            return 0

        logging.info("Fetching Davao City transit data from %s", args.endpoint)
        session = build_session(args.retries, args.backoff)
        try:
            result = fetch_overpass_data(
                session=session,
                endpoint=args.endpoint,
                query=QUERY,
                timeout_seconds=args.timeout,
                user_agent=args.user_agent,
            )
        finally:
            session.close()

        timestamp = utc_timestamp(result.accessed_at_utc)
        raw_dir = args.raw_dir.expanduser().resolve()
        raw_path = raw_dir / f"osm_davao_transit_elements_{timestamp}.json"
        metadata_path = raw_dir / (
            f"osm_davao_transit_elements_{timestamp}.metadata.json"
        )

        metadata = build_metadata(
            raw_path=raw_path,
            result=result,
            endpoint=args.endpoint,
            query=QUERY,
            timeout_seconds=args.timeout,
            retries=args.retries,
            user_agent=args.user_agent,
        )

        atomic_write_bytes(raw_path, result.content)
        atomic_write_json(metadata_path, metadata)

        logging.info(
            "Saved %s OSM elements (%s bytes) to %s",
            f"{metadata['response']['element_count']:,}",
            f"{metadata['response']['byte_count']:,}",
            raw_path,
        )
        logging.info("Saved source/date metadata to %s", metadata_path)
        return 0
    except IngestionError as exc:
        logging.error("Ingestion failed: %s", exc)
        return 1
    except OSError as exc:
        logging.error("Could not save output files: %s", exc)
        return 1
    except KeyboardInterrupt:
        logging.error("Ingestion cancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
