"""HTTP and storage contracts for the Observatory using the existing ETL fixture."""

from contextlib import closing, contextmanager
from http.client import HTTPConnection
import hashlib
import json
import sqlite3
from threading import Thread

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from scripts.observatory_app import Observatory, RELEASE_ROOT, server
from scripts.observatory_etl import build
from test_observatory_etl import record, workbook


@pytest.fixture
def release(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    book = tmp_path / "source.xlsx"
    workbook(book, [record(direction_1="Northbound", direction_2="Southbound", length_km_2="4")])
    geometry = LineString([(125.55, 7.05), (125.57, 7.08)])
    gpd.GeoDataFrame(geometry=[geometry], crs=4326).to_file(
        raw / "TEST.gpkg", layer="undirected", driver="GPKG", engine="pyogrio")
    folder = tmp_path / "release"
    build(book, raw, folder)
    return folder


@contextmanager
def running(root, store):
    app = Observatory(root, store)
    with server(app, 0) as http:
        thread = Thread(target=http.serve_forever)
        thread.start()
        try:
            yield http.server_port
        finally:
            http.shutdown()
            thread.join()


def request(port, path, payload=None, origin=None, host=None, mime="application/json"):
    headers = {}
    if origin is not None:
        headers["Origin"] = origin
    if host is not None:
        headers["Host"] = host
    if payload is not None:
        headers["Content-Type"] = mime
    with closing(HTTPConnection("127.0.0.1", port, timeout=10)) as conn:
        conn.request("GET" if payload is None else "POST", path,
                     None if payload is None else json.dumps(payload), headers=headers)
        result = conn.getresponse()
        body = result.read()
        return result.status, json.loads(body) if result.headers["Content-Type"].startswith("application/json") else body


def check_restart(root, store, actual=False):
    pointer = json.loads((root / "latest.json").read_text(encoding="utf-8"))
    release_db = root / pointer["release"] / "observatory.sqlite"
    before = hashlib.sha256(release_db.read_bytes()).hexdigest()
    with running(root, store) as port:
        assert request(port, "/private/")[0] == 200
        assert request(port, "/private/app.js")[0] == 200
        status, health = request(port, "/api/health")
        assert status == 200 and health["release_version"] == pointer["version"]
        status, lines = request(port, "/api/features?limit=100")
        assert status == 200 and lines["total"] > 0
        if actual:
            assert lines["total"] == health["statistics"]["feature_statuses"]["geometry_pass"]
        mapped_ids = set()
        for offset in range(0, lines["total"], 100):
            _, features = request(port, f"/api/features?limit=100&offset={offset}")
            mapped_ids.update(rid for feature in features["features"] for rid in feature["properties"]["route_ids"])
        offset = 0
        case = None
        while True:
            _, cases = request(port, f"/api/cases?limit=100&offset={offset}")
            case = next((item for item in cases["items"] if item["route_id"] in mapped_ids), None)
            if case or offset + 100 >= cases["total"]:
                break
            offset += 100
        assert case, "Need a real unresolved case linked to a displayed source line"
        _, route = request(port, "/api/routes/" + case["route_id"])
        assert any(item["issue_id"] == case["issue_id"] for item in route["cases"])
        path = "/api/cases/" + case["issue_id"]
        _, details = request(port, path)
        assert details["route"]["directions"] and details["source_features"] and details["history"] == []
        assert any(item["association_status"] == "unresolved" for item in details["route"]["directions"])
        payload = dict(decision="request_evidence", reviewer="Local QA", note="Test decision in a temporary store.",
                       release_version=health["release_version"])
        origin = f"http://127.0.0.1:{port}"
        assert request(port, path + "/reviews", payload, origin="https://example.org")[0] == 403
        assert request(port, path + "/reviews", {**payload, "release_version": "obsolete"}, origin=origin)[0] == 409
        assert request(port, path + "/reviews", {**payload, "note": "   "}, origin=origin)[0] == 400
        status, saved = request(port, path + "/reviews", payload, origin=origin)
        assert status == 201 and saved["created_at"].endswith("+00:00")
        assert saved["issue_id"] == case["issue_id"]
    with running(root, store) as port:
        assert request(port, path)[1]["history"] == [saved]
        status, second = request(port, path + "/reviews", {**payload, "decision": "keep_unresolved"},
                                 origin=f"http://127.0.0.1:{port}")
        assert status == 201
        assert request(port, path)[1]["history"] == [second, saved]
    with closing(sqlite3.connect(store)) as db:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("UPDATE reviews SET note='changed'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            db.execute("DELETE FROM reviews")
    assert hashlib.sha256(release_db.read_bytes()).hexdigest() == before


def test_review_workflow_restarts(release, tmp_path):
    check_restart(release, tmp_path / "reviews.sqlite")


def test_actual_private_release_restarts(tmp_path):
    if not (RELEASE_ROOT / "latest.json").is_file():
        pytest.skip("Private LTFRB release is available only in the local workspace.")
    check_restart(RELEASE_ROOT, tmp_path / "reviews.sqlite", actual=True)


def test_filters_bounds_and_private_file_boundary(release, tmp_path):
    with running(release, tmp_path / "reviews.sqlite") as port:
        assert request(port, "/api/routes?mode=PUB")[1]["total"] == 0
        assert request(port, "/api/routes?mode=PUJ&classification=EXISTING&q=test")[1]["total"] == 1
        assert request(port, "/api/routes?classification=IRIP")[1]["total"] == 0
        assert request(port, "/api/routes?limit=101")[0] == 400
        assert request(port, "/api/routes?mode=PUJ&mode=PUB")[0] == 400
        assert request(port, "/api/routes?mode=unknown")[0] == 400
        assert request(port, "/api/features?bbox=NaN,0,1,2")[0] == 400
        assert request(port, "/api/features?bbox=126,7,125,8")[0] == 400
        # This rectangle is inside the line's bounding box, but misses the line.
        assert request(port, "/api/features?bbox=125.55,7.075,125.551,7.08")[1]["total"] == 0
        status, hits = request(port, "/api/features?bbox=125.55,7.05,125.56,7.06")
        assert status == 200 and hits["total"] == 1 and hits["mode_counts"]["PUJ"] == 1
        assert request(port, "/api/routes/missing")[0] == 404
        assert request(port, "/api/cases/missing")[0] == 404
        assert request(port, "/private/../../data/processed/ltfrb_observatory/latest.json")[0] == 404
        assert request(port, "/api/health", host="untrusted.example")[0] == 403


def test_rejects_tampering_and_unsafe_store(release, tmp_path):
    pointer = json.loads((release / "latest.json").read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="outside"):
        Observatory(release, release / pointer["release"] / "reviews.sqlite")
    feature_file = release / pointer["release"] / "features.json"
    feature_file.write_bytes(feature_file.read_bytes() + b" ")
    with pytest.raises(ValueError, match="modified"):
        Observatory(release, tmp_path / "reviews.sqlite")
    assert not (tmp_path / "reviews.sqlite").exists()
