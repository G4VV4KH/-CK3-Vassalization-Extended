"""Check existing-release identity gates and isolated publication generation."""

from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ve_publication", ROOT / "tools/render_publication.py")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


class MetadataRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.output = self.root / "output"
        for name in ["tools/render_publication.py", "tools/render_readme.py", "publishing/description.en.md"]:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        for gallery in (ROOT / "publishing/media/gallery").glob("*.jpg"):
            target = self.source / "publishing/media/gallery" / gallery.name
            target.parent.mkdir(parents=True, exist_ok=True)
            # Gallery content is opaque to this text renderer; no real game files
            # or image editing are needed to exercise the write boundary.
            target.write_bytes(b"test gallery bytes")
        (self.source / "runtime-sentinel.txt").write_text("must not change")
        source = (self.source / "publishing/description.en.md").read_text(encoding="utf-8")
        urls = renderer.platform_urls(source)
        version = re.search(r"\*\*Version ([0-9.]+)\*\*", source)[1]
        self.config = {
            "kind": "PUBLICATION_METADATA_REVISION", "mod": "vassalization_extended",
            "public_title": renderer.TITLE, "metadata_revision": "test-copy-r1",
            "version": version, "game_target": renderer.GAME_TARGET, "frozen_build_id": "test-frozen-build",
            "canonical_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "platform_urls": urls,
            "platform_ids": {
                "steam": parse_qs(urlparse(urls["steam"]).query)["id"][0],
                "paradox": re.search(r"/mods/([0-9]+)", urls["paradox"])[1],
                "nexus": re.search(r"/mods/([0-9]+)", urls["nexus"])[1],
            },
            "nexus_file_id": "987654", "nexus_file_version": version,
            "nexus_file_description": f"For CK3 {renderer.GAME_TARGET}",
            "runtime_changed": False, "game_payload_changed": False,
            "archives_rebuilt": False, "mod_version_changed": False,
        }
        self.config_path = self.root / "revision.json"

    def run_renderer(self, use_revision=True, candidate="release"):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        args = [sys.executable, "-B", str(self.source / "tools/render_publication.py"),
                "--candidate", candidate, "--output-dir", str(self.output), "--build-id", "test-frozen-build"]
        if use_revision:
            args += ["--metadata-revision", str(self.config_path)]
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

    def test_existing_identity_survives_deterministic_isolated_generation(self):
        before = hashes(self.source)
        result = self.run_renderer()
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((self.output / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["publication_status"], "PREPARED_EXTERNAL_VERIFICATION_PENDING")
        self.assertEqual(metadata["platform_ids"], self.config["platform_ids"])
        self.assertEqual(metadata["nexus_file_id"], "987654")
        self.assertEqual(metadata["nexus_file_version"], self.config["version"])
        self.assertIn("Nexus File ID: 987654", (self.output / "METADATA-UPDATE.txt").read_text(encoding="utf-8"))
        first = hashes(self.output)
        self.assertEqual(self.run_renderer().returncode, 0)
        self.assertEqual(hashes(self.output), first)
        self.assertEqual(hashes(self.source), before)

    def test_invalid_identity_rejected_before_creating_output(self):
        cases = [("version", "0.0.0"), ("nexus_file_id", None),
                 ("platform_ids", {}), ("game_target", "0.0"),
                 ("canonical_sha256", "stale"), ("archives_rebuilt", True)]
        for key, value in cases:
            with self.subTest(key=key):
                original = self.config[key]
                self.config[key] = value
                result = self.run_renderer()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())
                self.config[key] = original
        self.assertNotEqual(self.run_renderer(candidate="rc2").returncode, 0)
        self.assertFalse(self.output.exists())

    def test_first_release_without_revision_does_not_claim_existing_identity(self):
        result = self.run_renderer(use_revision=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        metadata = json.loads((self.output / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["publication_status"], "NOT_PUBLISHED")
        self.assertEqual(metadata["platform_ids"], {})
        self.assertNotIn("nexus_file_id", metadata)
        self.assertFalse((self.output / "METADATA-UPDATE.txt").exists())


if __name__ == "__main__":
    unittest.main()
