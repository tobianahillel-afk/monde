"""Real projected EPSG:3857 GeoPackage evidence -> WGS84 offline MONDE Mini."""
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest

from monde.geopackage_points import (
    _point, _line, _polygon, _multipoint, _multiline, _multipolygon,
    to_geojson, documents_for_layers,
)
from monde.world import WorldMini
from tests.test_world_geopackage import AT, CAP, build, point

RADIUS = 6378137.0


def web(lon, lat):
    return (RADIUS * math.radians(lon),
            RADIUS * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def binary(kind, coords, *, srs=3857, envelope=False):
    """Original local 2D WKB with independent GeoPackage header."""
    flags = 1 | (2 if envelope else 0)
    header = b"GP\x00" + bytes([flags]) + struct.pack("<i", srs)
    if envelope:
        xy = [p for sub in coords for p in sub] if kind in (5, 6) else coords
        if kind == 3:
            xy = [p for ring in coords for p in ring]
        if kind == 6:
            xy = [p for polygon in coords for ring in polygon for p in ring]
        xs, ys = zip(*xy)
        header += struct.pack("<dddd", min(xs), max(xs), min(ys), max(ys))
    def vertices(pts):
        return struct.pack("<I", len(pts)) + b"".join(
            struct.pack("<dd", x, y) for x, y in pts)
    if kind == 2:
        body = vertices(coords)
    elif kind == 3:
        body = struct.pack("<I", len(coords)) + b"".join(vertices(ring) for ring in coords)
    elif kind == 4:
        body = struct.pack("<I", len(coords)) + b"".join(
            b"\x01" + struct.pack("<I", 1) + struct.pack("<dd", *p) for p in coords)
    elif kind == 5:
        body = struct.pack("<I", len(coords)) + b"".join(
            b"\x01" + struct.pack("<I", 2) + vertices(line) for line in coords)
    elif kind == 6:
        body = struct.pack("<I", len(coords)) + b"".join(
            b"\x01" + struct.pack("<I", 3) + struct.pack("<I", len(polygon)) +
            b"".join(vertices(ring) for ring in polygon) for polygon in coords)
    else:
        raise AssertionError("unsupported fixture type")
    return header + b"\x01" + struct.pack("<I", kind) + body


def fixture(path, *, invalid=False):
    build(path)
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO gpkg_spatial_ref_sys VALUES (?,?,?,?,?,?)",
                   ("Web Mercator", 3857, "EPSG", 3857, "test definition", "fixture"))
        db.execute("CREATE TABLE projected_points (fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES ('projected_points','features','Projected points',3857)")
        db.execute("INSERT INTO gpkg_geometry_columns VALUES ('projected_points','geom','POINT',3857,0,0)")
        x, y = web(2.3522, 48.8566)
        db.execute("INSERT INTO projected_points VALUES (1,?,?)",
                   (point(x, y, srid=3857, envelope=True), "Projected survey"))
        db.execute("CREATE TABLE projected_routes (fid INTEGER PRIMARY KEY, geom BLOB NOT NULL, name TEXT)")
        db.execute("INSERT INTO gpkg_contents VALUES ('projected_routes','features','Projected traces',3857)")
        db.execute("INSERT INTO gpkg_geometry_columns VALUES ('projected_routes','geom','GEOMETRY',3857,0,0)")
        points = [web(2.35, 48.85), web(2.36, 48.86)]
        ring = [web(2.35,48.85), web(2.36,48.85), web(2.36,48.86),
                web(2.35,48.85)]
        db.execute("INSERT INTO projected_routes VALUES (10,?,?)",
                   (binary(2, points, envelope=True), "Projected route"))
        db.execute("INSERT INTO projected_routes VALUES (11,?,?)",
                   (binary(3, [ring], envelope=True), "Projected polygon"))
        db.execute("INSERT INTO projected_routes VALUES (12,?,?)",
                   (binary(4, points, envelope=True), "Projected multipoints"))
        db.execute("INSERT INTO projected_routes VALUES (13,?,?)",
                   (binary(5, [points], envelope=True), "Projected multiline"))
        db.execute("INSERT INTO projected_routes VALUES (14,?,?)",
                   (binary(6, [[ring]], envelope=True), "Projected multipolygon"))
        if invalid:
            db.execute("UPDATE gpkg_contents SET srs_id=9999 WHERE table_name='projected_routes'")
    return path


class WebMercatorGeoPackageTests(unittest.TestCase):
    def test_existing_wgs84_and_all_six_projected_geometry_decoders(self):
        x,y=web(2.3522,48.8566)
        p=_point(point(x,y,srid=3857,envelope=True))
        self.assertAlmostEqual(p[0],2.3522,places=7)
        self.assertAlmostEqual(p[1],48.8566,places=7)
        self.assertEqual(_point(point(2,48)),[2,48])
        pts=[web(2.35,48.85),web(2.36,48.86)]
        ring=[web(2.35,48.85),web(2.36,48.85),web(2.36,48.86),
              web(2.35,48.85)]
        self.assertEqual(len(_line(binary(2,pts,envelope=True))),2)
        self.assertEqual(len(_polygon(binary(3,[ring],envelope=True))[0]),4)
        self.assertEqual(len(_multipoint(binary(4,pts,envelope=True))),2)
        self.assertEqual(len(_multiline(binary(5,[pts],envelope=True))[0]),2)
        self.assertEqual(len(_multipolygon(binary(6,[[ring]],envelope=True))[0][0]),4)

    def test_original_projected_sqlite_reaches_bitemporal_model_and_html(self):
        with tempfile.TemporaryDirectory() as d:
            source=fixture(Path(d)/"projected.gpkg")
            original=source.read_bytes()
            geo=to_geojson(source,layer="projected_points")
            self.assertEqual(geo["features"][0]["properties"]["gpkg_source_srs"],"EPSG:3857")
            coords=geo["features"][0]["geometry"]["coordinates"]
            self.assertAlmostEqual(coords[0],2.3522,places=7)
            self.assertAlmostEqual(coords[1],48.8566,places=7)
            docs=documents_for_layers(source,source_id="survey",
                locator="dataset://original.gpkg",captured_at=CAP,
                valid_from="2026-01-01T00:00:00Z")
            world=WorldMini()
            world.append_documents(docs)
            reports=world.search_reports("gpkg_source_srs","EPSG:3857",AT,CAP)
            self.assertGreaterEqual(len(reports["matches"]),1)
            mapped=world.export_geojson_bbox([-180,-90,180,90],AT,CAP)
            projected=[f for f in mapped["features"] if
                       f["properties"].get("monde_gpkg_source_srs")=="EPSG:3857"]
            self.assertTrue(projected)
            self.assertTrue(all(
                f["properties"]["monde_coordinate_transform"]==
                "WEB_MERCATOR_TO_WGS84_DERIVED" for f in projected))
            out=Path(d)/"offline.html"
            command=[sys.executable,"-m","monde.map_view","--gpkg",str(source),
                "--gpkg-all-layers","--source-id","survey",
                "--source-locator","dataset://original.gpkg",
                "--captured-at",CAP,"--valid-from","2026-01-01T00:00:00Z",
                "--at",AT,"--known-at",CAP,"--output",str(out)]
            run=subprocess.run(command,capture_output=True,text=True,
                env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1]/"src")})
            self.assertEqual(run.returncode,0,run.stderr)
            page=out.read_text(encoding="utf-8")
            self.assertIn("EPSG:3857",page)
            self.assertIn("projected_routes",page)
            self.assertIn('"total_source_features":',page)
            self.assertEqual(original,source.read_bytes())

    def test_bad_metadata_or_one_invalid_projected_layer_fails_atomically(self):
        with tempfile.TemporaryDirectory() as d:
            source=fixture(Path(d)/"bad.gpkg",invalid=True)
            output=Path(d)/"must-not-exist.html"
            run=subprocess.run([sys.executable,"-m","monde.map_view",
                "--gpkg",str(source),"--gpkg-all-layers","--source-id","s",
                "--source-locator","dataset://bad","--captured-at",CAP,
                "--valid-from","2026-01-01T00:00:00Z","--at",AT,
                "--known-at",CAP,"--output",str(output)],
                capture_output=True,text=True,
                env={**os.environ,"PYTHONPATH":str(Path(__file__).resolve().parents[1]/"src")})
            self.assertNotEqual(run.returncode,0)
            self.assertFalse(output.exists())

    def test_bad_projected_bounds_envelope_and_header_srs_fail_closed(self):
        x,y=web(2.3522,48.8566)
        for geom in [point(float("nan"),y,srid=3857),
                     point(20037508.343,y,srid=3857),
                     point(x,float("inf"),srid=3857),
                     point(x,y,srid=9999)]:
            with self.subTest(geom=repr(geom)[:40]),self.assertRaises(ValueError):
                _point(geom)
        # Corrupt the source envelope while leaving the Point unchanged.
        bad=bytearray(point(x,y,srid=3857,envelope=True))
        struct.pack_into("<d",bad,8,x+100)
        with self.assertRaises(ValueError):
            _point(bytes(bad))
        # No accidental inference of a third coordinate from arbitrary WKB.
        with self.assertRaises(ValueError):
            _point(point(x,y,srid=3857)+struct.pack("<d",17.0))

    def test_layer_declared_3857_but_row_header_4326_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            src=fixture(Path(d)/"source.gpkg")
            with sqlite3.connect(src) as db:
                db.execute("UPDATE projected_points SET geom=? WHERE fid=1",
                           (point(2.35,48.86,srid=4326),))
            with self.assertRaises(ValueError):
                to_geojson(src,layer="projected_points")
