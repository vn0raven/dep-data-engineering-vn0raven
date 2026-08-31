"""
Load processed Davao transit CSV files into a local SQLite database.
"""

from pathlib import Path
import sqlite3

import pandas as pd


PROCESSED_DIR = Path("data/processed")
DATABASE_PATH = PROCESSED_DIR / "davao_transit.db"


def sql_value(value):
    """Convert pandas/numpy values into SQLite-friendly Python values."""
    if pd.isna(value):
        return None

    if hasattr(value, "item"):
        return value.item()

    return value


def rows_for_sql(dataframe):
    for row in dataframe.itertuples(index=False, name=None):
        yield tuple(sql_value(value) for value in row)


def load_data():
    stops = pd.read_csv(PROCESSED_DIR / "stops.csv")
    routes = pd.read_csv(PROCESSED_DIR / "routes.csv")
    route_stops = pd.read_csv(PROCESSED_DIR / "route_stops.csv")

    # Rebuild from scratch so repeated runs produce the same logical database.
    if DATABASE_PATH.exists():
        DATABASE_PATH.unlink()

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("PRAGMA foreign_keys = ON;")

        connection.executescript(
            """
            CREATE TABLE stops (
                stop_id TEXT PRIMARY KEY,
                osm_type TEXT NOT NULL,
                osm_id INTEGER NOT NULL,
                name TEXT,
                stop_type TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                public_transport TEXT,
                highway TEXT,
                amenity TEXT,
                bus TEXT,
                ferry TEXT,
                evidence TEXT NOT NULL,
                route_member_roles TEXT,
                source_file TEXT NOT NULL,

                UNIQUE (osm_type, osm_id),

                CHECK (
                    latitude IS NULL
                    OR latitude BETWEEN -90 AND 90
                ),

                CHECK (
                    longitude IS NULL
                    OR longitude BETWEEN -180 AND 180
                )
            );


            CREATE TABLE routes (
                route_id TEXT PRIMARY KEY,
                osm_relation_id INTEGER NOT NULL UNIQUE,
                route_ref TEXT,
                route_name TEXT,
                route_mode TEXT NOT NULL,
                operator TEXT,
                network TEXT,
                origin_name TEXT,
                destination_name TEXT,
                source_file TEXT NOT NULL,

                CHECK (route_mode IN ('bus', 'ferry'))
            );


            CREATE TABLE route_stops (
                route_id TEXT NOT NULL,
                stop_sequence INTEGER NOT NULL,
                member_index INTEGER NOT NULL,
                stop_id TEXT NOT NULL,
                member_osm_type TEXT NOT NULL,
                member_osm_id INTEGER NOT NULL,
                member_role TEXT NOT NULL,

                PRIMARY KEY (route_id, stop_sequence),

                FOREIGN KEY (route_id)
                    REFERENCES routes(route_id),

                FOREIGN KEY (stop_id)
                    REFERENCES stops(stop_id),

                CHECK (stop_sequence >= 1),
                CHECK (member_index >= 1)
            );
            """
        )

        connection.executemany(
            """
            INSERT INTO stops (
                stop_id,
                osm_type,
                osm_id,
                name,
                stop_type,
                latitude,
                longitude,
                public_transport,
                highway,
                amenity,
                bus,
                ferry,
                evidence,
                route_member_roles,
                source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_for_sql(stops),
        )

        connection.executemany(
            """
            INSERT INTO routes (
                route_id,
                osm_relation_id,
                route_ref,
                route_name,
                route_mode,
                operator,
                network,
                origin_name,
                destination_name,
                source_file
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows_for_sql(routes),
        )

        connection.executemany(
            """
            INSERT INTO route_stops (
                route_id,
                stop_sequence,
                member_index,
                stop_id,
                member_osm_type,
                member_osm_id,
                member_role
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows_for_sql(route_stops),
        )

        connection.commit()

        stop_count = connection.execute(
            "SELECT COUNT(*) FROM stops"
        ).fetchone()[0]

        route_count = connection.execute(
            "SELECT COUNT(*) FROM routes"
        ).fetchone()[0]

        route_stop_count = connection.execute(
            "SELECT COUNT(*) FROM route_stops"
        ).fetchone()[0]

        print("SQLite database created successfully.")
        print(f"Database: {DATABASE_PATH}")
        print(f"Stops: {stop_count}")
        print(f"Routes: {route_count}")
        print(f"Route-stop occurrences: {route_stop_count}")

    finally:
        connection.close()


if __name__ == "__main__":
    load_data()