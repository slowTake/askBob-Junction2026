"""Tests for the pure parts of demo_snapshot.py. Run: python3 scripts/demo_snapshot_test.py"""

import gzip
import unittest

from demo_snapshot import asset_path, mesh_body, parse_sse, snapshot_json


class ParseSse(unittest.TestCase):
    def test_reads_events_in_order(self) -> None:
        text = 'event: step\ndata: {"tool": "a"}\n\nevent: answer\ndata: {"answer": "x"}\n\n'
        self.assertEqual(
            parse_sse(text),
            [
                {"event": "step", "data": '{"tool": "a"}'},
                {"event": "answer", "data": '{"answer": "x"}'},
            ],
        )

    def test_skips_keepalives_and_joins_data_lines(self) -> None:
        # By the SSE spec: ":" lines are comments; several data lines join with "\n";
        # a block with no event field is a "message"; CRLF counts as a line break.
        text = ": ping\r\n\r\ndata: one\r\ndata: two\r\n\r\n"
        self.assertEqual(parse_sse(text), [{"event": "message", "data": "one\ntwo"}])

    def test_keeps_an_unterminated_last_event(self) -> None:
        self.assertEqual(parse_sse("event: error\ndata: {}"), [{"event": "error", "data": "{}"}])


class AssetPath(unittest.TestCase):
    def test_matches_the_frontend_layout(self) -> None:
        # The same paths as assetPath in frontend/src/demo/snapshot.ts.
        self.assertEqual(asset_path("d1", "page", 2), "documents/d1/page-2.png")
        self.assertEqual(asset_path("d1", "elements", 0), "documents/d1/elements-0.json")
        self.assertEqual(asset_path("d1", "upscale", 1), "documents/d1/upscale-1.json")
        self.assertEqual(asset_path("d1", "mesh"), "documents/d1/mesh.json")
        self.assertEqual(asset_path("d1", "ifc"), "documents/d1/model.ifc")


class MeshBody(unittest.TestCase):
    def test_unzips_a_gzipped_mesh(self) -> None:
        # The API stores meshes gzipped and says so in Content-Encoding.
        self.assertEqual(mesh_body(gzip.compress(b'{"meshes": []}'), "gzip"), b'{"meshes": []}')

    def test_keeps_a_plain_mesh(self) -> None:
        self.assertEqual(mesh_body(b'{"meshes": []}', None), b'{"meshes": []}')


class SnapshotJson(unittest.TestCase):
    def test_lists_recorded_upscales_per_document(self) -> None:
        snap = snapshot_json(
            recorded_at="2026-11-17",
            health={"postgres": True},
            documents=[{"id": "d1"}, {"id": "d2"}],
            upscales={"d1": [0, 2]},
            recordings=[],
        )
        self.assertEqual(snap["recorded_at"], "2026-11-17")
        self.assertEqual(snap["upscales"], {"d1": [0, 2], "d2": []})
        self.assertEqual([d["id"] for d in snap["documents"]], ["d1", "d2"])


if __name__ == "__main__":
    unittest.main()
