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


class ParadoxRichTextTests(unittest.TestCase):
    def setUp(self):
        self.source = (ROOT / "publishing/description.en.md").read_text(encoding="utf-8")

    def test_real_copy_preserves_native_headings_lists_links_and_visible_content(self):
        output = renderer.paradox_rich_html(self.source)
        checks = renderer.validate_paradox_rich_html(self.source, output)
        self.assertTrue(all(check["passed"] for check in checks))
        self.assertIn("<h3>At a glance</h3><ul><li>", output)
        self.assertIn("<h3>Getting started</h3><ol><li>", output)
        self.assertIn("<h3>My mods</h3><ul><li><a href=", output)
        self.assertIn("<strong>Version 0.2.1</strong>", output)
        with self.assertRaisesRegex(ValueError, "semantic_section_headings"):
            renderer.validate_paradox_rich_html(self.source, output.replace("<h3>At a glance</h3>", "<p>At a glance</p>"))
        with self.assertRaisesRegex(ValueError, "semantic_list_groups"):
            renderer.validate_paradox_rich_html(self.source, output.replace("<ol>", "<p>").replace("</ol>", "</p>"))

    def test_raw_html_and_link_attributes_are_escaped(self):
        output = renderer.paradox_rich_html('## Safe <script>\n\n- [A & B](https://example.com/?a=1&b=2)\n\nA <tag> and `code`.\n')
        self.assertNotIn("<script>", output)
        self.assertNotIn("<tag>", output)
        self.assertIn("<h3>Safe &lt;script&gt;</h3>", output)
        self.assertIn('<a href="https://example.com/?a=1&amp;b=2">A &amp; B</a>', output)
        self.assertIn("<strong>code</strong>", output)

    def test_actual_rich_html_limit_counts_astral_characters_as_utf16_pairs(self):
        base_units = len(renderer.paradox_rich_html(self.source).encode("utf-16-le")) // 2
        source = self.source + "\n" + "💛" * ((10000 - base_units) // 2 + 1) + "\n"
        output = renderer.paradox_rich_html(source)
        self.assertLess(len(output), 10000)
        self.assertGreaterEqual(len(output.encode("utf-16-le")) // 2, 10000)
        with self.assertRaisesRegex(ValueError, "under_10000_utf16_units"):
            renderer.validate_paradox_rich_html(source, output)


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
