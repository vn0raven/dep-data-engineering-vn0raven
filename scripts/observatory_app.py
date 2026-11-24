"""Run the private Observatory on this computer using the existing GIS environment."""

import argparse
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, unquote, urlsplit

from shapely.geometry import box, shape

from scripts.verify_observatory import verify

ROOT = Path(__file__).resolve().parents[1]
RELEASE_ROOT = ROOT / "data/processed/ltfrb_observatory"
REVIEW_DB = ROOT / "reports/observatory-private/m6-reviews.sqlite"
WEB = ROOT / "dashboard/observatory"
DISPOSITIONS = ("keep_unresolved", "request_evidence", "document_review")
MODES = ("PUJ", "PUB", "UV_EXPRESS")
CLASSES = ("EXISTING", "IRIP")
ROUTE_FIELDS = "route_id, route_name, mode, classification, metadata_status, review_status"
STATIC = {"": ("index.html", "text/html"), "app.js": ("app.js", "text/javascript"),
          "style.css": ("style.css", "text/css"), "explorer.js": ("explorer.js", "text/javascript")}


class RequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def read_bbox(value):
    if not value:
        return None
    try:
        west, south, east, north = map(float, value.split(","))
    except ValueError:
        raise RequestError("Use four coordinates: west, south, east, north.") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise RequestError("Bounds must be ordered longitude and latitude values.")
    return box(west, south, east, north)


def options(query, allowed, max_limit=100):
    if query.keys() - allowed or any(len(values) != 1 for values in query.values()):
        raise RequestError("Unknown or repeated query parameter.")
    values = {key: items[0] for key, items in query.items()}
    try:
        limit = int(values.pop("limit", str(min(40, max_limit))))
        offset = int(values.pop("offset", "0"))
    except ValueError:
        raise RequestError("Limit and offset must be integers.") from None
    if not 1 <= limit <= max_limit or not 0 <= offset <= 10000:
        raise RequestError(f"Limit must be 1–{max_limit} and offset 0–10000.")
    for key, choices in (("mode", MODES), ("classification", CLASSES)):
        if values.get(key) and values[key] not in choices:
            raise RequestError(f"Unknown {key}.")
    if len(values.get("q", "")) > 100:
        raise RequestError("Search must be at most 100 characters.")
    return values, limit, offset


def page(rows, limit, offset):
    return {"items": rows[offset:offset + limit], "total": len(rows),
            "limit": limit, "offset": offset}


class Observatory:
    def __init__(self, release_root, review_db):
        if not __debug__:
            raise ValueError("Release verification requires Python assertions.")
        release_root = Path(release_root).resolve()
        pointer = json.loads((release_root / "latest.json").read_text(encoding="utf-8"))
        self.version = pointer["version"]
        if not re.fullmatch(r"[0-9a-f]{20}", self.version):
            raise ValueError("Invalid release version.")
        self.release = release_root / "releases" / self.version
        if pointer["release"] != f"releases/{self.version}" or self.release.resolve() != self.release:
            raise ValueError("Invalid release pointer.")
        manifest = json.loads((self.release / "manifest.json").read_text(encoding="utf-8"))
        outputs = {entry["path"] for entry in manifest["outputs"]}
        required = {"observatory.sqlite", "geometry_pass.geojson", "geometry_pass.gpkg",
                    "routes.json", "directions.json", "route_localities.json", "assets.json",
                    "layers.json", "features.json", "associations.json", "transformations.json", "issues.json"}
        if (not required <= outputs or any(
            Path(name).name != name or (self.release / name).is_symlink() for name in outputs
        )):
            raise ValueError("Missing or unsafe release manifest entries.")
        self.verification = verify(self.release)
        if self.verification["version"] != self.version:
            raise ValueError("Release identity mismatch.")
        self.release_db = self.release / "observatory.sqlite"
        self.review_db = Path(review_db).resolve()
        if self.review_db == release_root or release_root in self.review_db.parents:
            raise ValueError("Keep review storage outside the release tree.")
        # Fixed application runtime location by default. Custom stores must be new
        # files or existing stores initialized by this application.
        exists = self.review_db.exists()
        if not exists:
            self.review_db.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.review_db)) as connection:
            if exists and connection.execute("PRAGMA application_id").fetchone()[0] != 0x4F425336:
                raise ValueError("Review database is not an Observatory review store.")
            connection.executescript("""
                PRAGMA application_id = 1329746742;
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY,
                    release_version TEXT NOT NULL,
                    issue_id TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS reviews_case ON reviews(release_version, issue_id, id);
                CREATE TRIGGER IF NOT EXISTS reviews_no_update BEFORE UPDATE ON reviews
                    BEGIN SELECT RAISE(ABORT, 'Review history is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS reviews_no_delete BEFORE DELETE ON reviews
                    BEGIN SELECT RAISE(ABORT, 'Review history is append-only'); END;
            """)

    @contextmanager
    def read_release(self):
        with closing(sqlite3.connect(self.release_db.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            yield db

    def routes(self, query, geometry=False):
        allowed = {"mode", "classification", "q", "limit", "offset"}
        values, limit, offset = options(query, allowed | ({"bbox"} if geometry else set()),
                                        max_limit=100)
        area = read_bbox(values.get("bbox"))
        with self.read_release() as db:
            routes = [dict(row) for row in db.execute(
                f"SELECT {ROUTE_FIELDS}, file_id FROM routes ORDER BY route_name, route_id")]
            term = values.get("q", "").casefold()
            routes = [row for row in routes if (
                (not values.get("mode") or row["mode"] == values["mode"]) and
                (not values.get("classification") or row["classification"] == values["classification"]) and
                (not term or term in (row["route_name"] or "").casefold() or term in row["route_id"].casefold())
            )]
            if not geometry:
                return page(routes, limit, offset)
            by_file = {}
            for route in routes:
                by_file.setdefault(route["file_id"], []).append(route["route_id"])
            route_ids = {route["route_id"] for route in routes}
            candidates = {}
            for row in db.execute("""
                SELECT a.feature_id, d.route_id FROM associations a
                JOIN directions d USING(direction_id) WHERE a.association_status='candidate'
            """):
                if row["route_id"] in route_ids:
                    candidates.setdefault(row["feature_id"], set()).add(row["route_id"])
            features = []
            matching_routes = set()
            for row in db.execute("""
                SELECT feature_id, file_id, layer_id, geometry_json, status FROM features
                WHERE status='geometry_pass' ORDER BY feature_id
            """):
                related = by_file.get(row["file_id"], [])
                if not related:
                    continue
                line = json.loads(row["geometry_json"])
                if area is not None and not shape(line).intersects(area):
                    continue
                matching_routes.update(related)
                features.append({"type": "Feature", "id": row["feature_id"], "geometry": line,
                                 "properties": {"route_ids": related, "status": row["status"],
                                                "file_id": row["file_id"], "layer_id": row["layer_id"],
                                                "candidate_route_ids": sorted(candidates.get(row["feature_id"], ()))}})
        result = page(features, limit, offset)
        return {"type": "FeatureCollection", "features": result.pop("items"), **result,
                "mode_counts": {mode: len({r["route_id"] for r in routes
                                           if r["route_id"] in matching_routes and r["mode"] == mode})
                                for mode in MODES},
                "comparison": "Intersections with documented lines linked by source file."}

    def route(self, route_id):
        with self.read_release() as db:
            record = db.execute(f"""
                SELECT {', '.join('r.' + field.strip() for field in ROUTE_FIELDS.split(','))},
                       r.source_record_id, r.source_excel_row, r.file_id, r.navigation_status,
                       assets.status AS source_status
                FROM routes r LEFT JOIN assets USING(file_id) WHERE route_id=?
            """, (route_id,)).fetchone()
            if record is None:
                raise RequestError("Route record not found.", 404)
            directions = db.execute("""
                SELECT d.direction_id, d.ordinal, d.direction, d.declared_km, d.metadata_status,
                       a.association_status, a.feature_id, a.match_method, a.reason, a.length_screen
                FROM directions d LEFT JOIN associations a USING(direction_id)
                WHERE d.route_id=? ORDER BY d.ordinal
            """, (route_id,))
            cases = db.execute("""
                SELECT issue_id, code, severity, detail FROM issues
                WHERE (entity_type='route' AND entity_id=?) OR (entity_type='direction' AND
                    entity_id IN (SELECT direction_id FROM directions WHERE route_id=?))
                ORDER BY code, issue_id LIMIT 100
            """, (route_id, route_id))
            localities = db.execute("SELECT DISTINCT locality_name FROM route_localities JOIN directions USING(direction_id) WHERE route_id=?", (route_id,)).fetchall()
            return {**dict(record), "localities": [dict(row) for row in localities], "directions": list(map(dict, directions)),
                    "cases": list(map(dict, cases))}

    def cases(self, query):
        _, limit, offset = options(query, {"limit", "offset"})
        with self.read_release() as db:
            rows = db.execute("""
                SELECT i.issue_id, i.code, i.severity, d.route_id, r.route_name, d.ordinal
                FROM issues i JOIN directions d
                    ON i.entity_type='direction' AND i.entity_id=d.direction_id
                JOIN routes r ON r.route_id=d.route_id
                WHERE i.code='unresolved_geometry_association'
                ORDER BY r.route_name, d.ordinal, i.issue_id
            """)
            result = page(list(map(dict, rows)), limit, offset)
            for item in result['items']:
                item['project_review_count'] = len(self.history(item['issue_id']))
            return result

    def case(self, issue_id):
        with self.read_release() as db:
            issue = db.execute("SELECT * FROM issues WHERE issue_id=?", (issue_id,)).fetchone()
            if issue is None or issue["entity_type"] not in ("route", "direction"):
                raise RequestError("Review case not found.", 404)
            route_id = issue["entity_id"]
            if issue["entity_type"] == "direction":
                route_id = db.execute("SELECT route_id FROM directions WHERE direction_id=?",
                                      (route_id,)).fetchone()[0]
            route = self.route(route_id)
            evidence = db.execute("""
                SELECT f.feature_id, f.status, f.reason, f.geodesic_km, l.source_crs
                FROM features f JOIN layers l USING(layer_id)
                WHERE f.file_id=? ORDER BY f.feature_id LIMIT 100
            """, (route["file_id"],))
            return {"issue": dict(issue), "route": route, "release_version": self.version,
                    "source_features": list(map(dict, evidence)),
                    "history": self.history(issue_id)}

    def history(self, issue_id):
        with closing(sqlite3.connect(self.review_db)) as db:
            db.row_factory = sqlite3.Row
            rows = db.execute("""
                SELECT * FROM reviews WHERE release_version=? AND issue_id=?
                ORDER BY id DESC LIMIT 100
            """, (self.version, issue_id))
            return list(map(dict, rows))

    def save(self, issue_id, payload):
        if not isinstance(payload, dict) or set(payload) != {"decision", "reviewer", "note", "release_version"}:
            raise RequestError("Provide decision, reviewer, note and release version.")
        if payload["release_version"] != self.version:
            raise RequestError("The active release changed. Reload the case before saving.", 409)
        decision, reviewer, note = (payload[key] for key in ("decision", "reviewer", "note"))
        if decision not in DISPOSITIONS:
            raise RequestError("Choose a supported project decision.")
        for item, maximum in ((reviewer, 80), (note, 2000)):
            if not isinstance(item, str) or not 1 <= len(item.strip()) <= maximum:
                raise RequestError(f"Reviewer and note are required (80 and 2000 characters maximum).")
        self.case(issue_id)
        event = {"release_version": self.version, "issue_id": issue_id, "decision": decision,
                 "reviewer": reviewer.strip(), "note": note.strip(),
                 "created_at": datetime.now(timezone.utc).isoformat()}
        with closing(sqlite3.connect(self.review_db)) as db, db:
            cursor = db.execute("""
                INSERT INTO reviews (release_version, issue_id, decision, reviewer, note, created_at)
                VALUES (:release_version, :issue_id, :decision, :reviewer, :note, :created_at)
            """, event)
            return {**event, "id": cursor.lastrowid}


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def respond(self, status, content, mime="application/json"):
        data = json.dumps(content, ensure_ascii=True).encode() if mime == "application/json" else content
        self.send_response(status)
        self.send_header("Content-Type", mime + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        app = self.server.app
        host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get_all("Host") != [host]:
            raise RequestError("Use the printed local address.", 403)
        url = urlsplit(self.path)
        path = url.path
        query = parse_qs(url.query, keep_blank_values=True, max_num_fields=10)
        if self.command == "POST":
            review = re.fullmatch(r"/api/cases/([\w-]+)/reviews", path)
            if not review or query:
                raise RequestError("Endpoint not found.", 404)
            if self.headers.get_all("Origin") != [f"http://{host}"]:
                raise RequestError("Review writes require the local app origin.", 403)
            if self.headers.get_content_type() != "application/json":
                raise RequestError("Send an application/json review.", 415)
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise RequestError("Invalid Content-Length.") from None
            if not 1 <= size <= 16384:
                raise RequestError("Review request is empty or too large.", 413)
            payload = json.loads(self.rfile.read(size))
            return self.respond(201, app.save(review[1], payload))
        if path.startswith("/private/") and path.removeprefix("/private/") in STATIC:
            filename, mime = STATIC[path.removeprefix("/private/")]
            return self.respond(200, (WEB / filename).read_bytes(), mime)
        if path in ("/api/health", "/api/quality") and not query:
            return self.respond(200, {"release_version": app.version,
                                      "verification": app.verification["status"],
                                      "statistics": app.verification["statistics"]})
        if path in ("/api/routes", "/api/features"):
            return self.respond(200, app.routes(query, geometry=path.endswith("features")))
        if path == "/api/cases":
            return self.respond(200, app.cases(query))
        item = re.fullmatch(r"/api/(routes|cases)/([^/]{1,160})", path)
        if item and not query:
            lookup = app.route if item[1] == "routes" else app.case
            return self.respond(200, lookup(unquote(item[2])))
        raise RequestError("Endpoint not found.", 404)

    def handle_request(self):
        try:
            self.dispatch()
        except RequestError as error:
            self.respond(error.status, {"error": str(error)})
        except (ValueError, UnicodeError):
            self.respond(400, {"error": "Malformed request."})
        except (OSError, sqlite3.Error):
            self.respond(503, {"error": "Local storage is unavailable."})

    do_GET = handle_request
    do_POST = handle_request

    def log_message(self, *_):
        # Request paths can contain private route and case identifiers.
        pass


def server(app, port):
    http = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    http.app = app
    return http


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-root", type=Path, default=RELEASE_ROOT)
    parser.add_argument("--review-db", type=Path, default=REVIEW_DB)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535.")
    try:
        app = Observatory(args.release_root, args.review_db)
        with server(app, args.port) as http:
            print(f"Private Observatory: http://127.0.0.1:{http.server_port}/private/",
                  flush=True)
            http.serve_forever()
    except KeyboardInterrupt:
        return
    except (OSError, ValueError, KeyError, AssertionError, sqlite3.Error):
        parser.exit(1, "Observatory startup failed. Verify the release and review-store configuration.\n")


if __name__ == "__main__":
    main()
