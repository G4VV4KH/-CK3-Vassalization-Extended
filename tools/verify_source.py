"""Shared script parser and historical 0.1.0 check; CLI runs the current profile verifier."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CB = Path("common/casus_belli_types/00_vassalization.txt")
KEY = "game_concept_vassalize_casus_belli_desc"
TOKEN = re.compile(r'\s+|\#[^\r\n]*|"(?:\\.|[^"\\])*"|[{}]|>=|<=|!=|\?=|=|>|<|[^\s{}=<>!?#"]+')


def parse(text):
    stream, end = [], 0
    for match in TOKEN.finditer(text):
        assert match.start() == end, f"Unrecognized input at {end}"
        end = match.end()
        token = match.group()
        if not token.isspace() and not token.startswith("#"):
            stream.append(token)
    assert end == len(text), "Unrecognized trailing input"
    pos = 0

    def block(nested=False):
        nonlocal pos
        entries = []
        while pos < len(stream) and stream[pos] != "}":
            assert pos + 2 < len(stream), "Incomplete assignment"
            key, op = stream[pos:pos + 2]
            assert op in {"=", ">=", "<=", "!=", "?=", ">", "<"}, (key, op)
            pos += 2
            if stream[pos] == "{":
                pos += 1
                value = block(True)
            else:
                value = stream[pos]
                pos += 1
            entries.append((key, op, value))
        if nested:
            assert pos < len(stream) and stream[pos] == "}", "Unclosed block"
            pos += 1
        return entries

    result = block()
    assert pos == len(stream), "Unmatched closing brace"
    return result


def only(entries, key):
    matches = [entry for entry in entries if entry[0] == key]
    assert len(matches) == 1, (key, len(matches))
    return matches[0][2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    upstream = (args.game_root / CB).read_bytes()
    recorded = json.loads((ROOT / "docs/upstream.json").read_text(encoding="utf-8"))
    assert sha(upstream) == recorded["cb_sha256"], "Upstream changed: review and rebase before testing"
    vanilla = parse(upstream.decode("utf-8-sig"))
    payload = (ROOT / CB).read_bytes()
    modified = parse(payload.decode("utf-8-sig"))
    assert len(vanilla) == len(modified) == 1
    vanilla_cb = only(vanilla, "vassalization_cb")
    gate = only(vanilla_cb, "allowed_against_character_display_regardless")
    removed = only(gate, "scope:defender")
    expected = [("custom_description", "=", [
        ("text", "=", '"vassalization_cb_target_too_many_counties"'),
        ("subject", "=", "scope:defender"),
        ("NOT", "=", [("any_sub_realm_county", "=", [("count", ">", "vassalization_size_limit")])]),
    ])]
    assert removed == expected, "The removed block no longer contains only the county cap"
    gate[:] = [entry for entry in gate if entry[0] != "scope:defender"]
    assert modified == vanilla, "Unexpected changes outside the county cap"
    assert "vassalization_size_limit" not in payload.decode("utf-8-sig")
    assert not (ROOT / "common/character_interactions").exists(), "Diplomacy changes are outside this prototype"
    descriptor = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    assert "replace_path" not in descriptor
    assert 'name="[DEV] Vassalization Extended"' in descriptor
    assert 'supported_version="1.20.*"' in descriptor
    for language in ("english", "russian"):
        path = ROOT / f"localization/replace/vassalization_extended_l_{language}.yml"
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf"), "CK3 localization requires UTF-8 BOM"
        text = raw.decode("utf-8-sig")
        assert text.startswith(f"l_{language}:\n")
        assert len(text.splitlines()) == 2 and f" {KEY}:0 " in text
        assert "vassalize_default_size" not in text and "vassalize_growth_per_innovation" not in text
        assert text.count('"') == 2, "Unescaped localization quotes"
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "STATIC_CHECKS_PASSED",
        "game_version": recorded["game_version"],
        "upstream_sha256": sha(upstream),
        "mod_cb_sha256": sha(payload),
        "checks": ["pinned upstream identity", "script token and block structure", "only the county gate removed",
                   "all other CB subtrees unchanged", "no diplomatic interaction override", "no replace_path",
                   "DEV descriptor", "English and Russian localization BOM and key"],
        "engine_test_performed": False,
        "engine_validation": "NOT_ASSESSED_BY_THIS_STATIC_CHECK: see docs/playtests for recorded engine evidence",
    }
    if args.write_report:
        (ROOT / "docs/verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    from verify_profiles import main as verify_current_profiles
    verify_current_profiles()
