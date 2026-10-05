"""Build/check the pinned vanilla subject-group overlay for religious peace terms.

Only append ve_religious_protection to the end of each non-tributary group's
contracts list. Appending preserves the numeric indices of existing obligations
in saves. All vanilla fields and all tributary groups remain byte-for-byte intact.
An upstream hash mismatch requires a deliberate source review and pin update.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re
import sys


MOD_ROOT = Path(__file__).resolve().parents[1]
GROUP_PATH = Path("common/subject_contracts/groups/subject_contract_groups.txt")
UPSTREAM_VERSION = "1.20.0.3"
UPSTREAM_SHA256 = "a2e3cf78c5dae7e6656b8e95d5f88a9b8584909d3908496828b0a47ce41056ea"
OBLIGATION = "ve_religious_protection"
EXPECTED_GROUPS = (
    "feudal_vassal", "republic_vassal", "theocracy_vassal", "clan_vassal",
    "tribal_vassal", "admin_vassal", "nomad_vassal", "herder_vassal",
    "celestial_vassal", "mandala_vassal", "japan_administrative_vassal",
    "japan_feudal_vassal", "wanua_vassal", "meritocratic_vassal",
)
TOP_BLOCK = re.compile(r"(?m)^\ufeff?([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{")
STRUCTURE = re.compile(r'"(?:\\.|[^"\\])*"|#[^\r\n]*|[{}]')
CONTRACT_BLOCK = re.compile(r"(?m)^\tcontracts\s*=\s*\{")
TRIBUTARY = re.compile(r"(?m)^\tis_tributary\s*=\s*yes\s*$")


def block_end(text: str, opening: int) -> int:
    depth = 0
    for match in STRUCTURE.finditer(text, opening):
        token = match.group()
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth == 0:
                return match.end()
    raise ValueError(f"Unclosed block at offset {opening}")


def blocks(text: str) -> dict[str, tuple[int, int, str]]:
    result: dict[str, tuple[int, int, str]] = {}
    previous_end = 0
    for match in TOP_BLOCK.finditer(text):
        if match.start() < previous_end:
            raise ValueError("Unexpected nested unindented definition")
        name = match.group(1)
        if name in result:
            raise ValueError(f"Duplicate group: {name}")
        end = block_end(text, match.end() - 1)
        result[name] = (match.start(), end, text[match.start():end])
        previous_end = end
    return result


def contract_list(group: str) -> tuple[int, int, list[str]]:
    matches = list(CONTRACT_BLOCK.finditer(group))
    if len(matches) != 1:
        raise ValueError("Expected exactly one contracts list in each group")
    start = matches[0].end()
    end = block_end(group, start - 1) - 1
    tokens = group[start:end].split()
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token) for token in tokens):
        raise ValueError("Contracts list contains unexpected syntax")
    return start, end, tokens


def build(upstream: bytes) -> bytes:
    actual_hash = hashlib.sha256(upstream).hexdigest()
    if actual_hash != UPSTREAM_SHA256:
        raise ValueError(
            f"Upstream {GROUP_PATH} changed; expected {UPSTREAM_VERSION} SHA256 "
            f"{UPSTREAM_SHA256}, found {actual_hash}. Review before updating the pin."
        )
    source = upstream.decode("utf-8")
    newline = "\r\n" if "\r\n" in source else "\n"
    groups = blocks(source)
    eligible = tuple(name for name, (_, _, body) in groups.items() if not TRIBUTARY.search(body))
    if eligible != EXPECTED_GROUPS:
        raise ValueError(f"Unexpected non-tributary group inventory: {eligible}")
    inserts = []
    for name in eligible:
        start, _, body = groups[name]
        _, list_end, old_names = contract_list(body)
        if OBLIGATION in old_names:
            raise ValueError(f"Upstream already contains {OBLIGATION}: {name}")
        # list_end points at }, preceded by the vanilla one-tab indentation.
        if body[list_end - 1:list_end] != "\t":
            raise ValueError(f"Unexpected contracts closing indentation: {name}")
        inserts.append((start + list_end - 1, f"\t\t{OBLIGATION}{newline}"))
    result = source
    for offset, addition in reversed(inserts):
        result = result[:offset] + addition + result[offset:]
    verify_semantic_delta(source, result)
    return result.encode("utf-8")


def verify_semantic_delta(source: str, generated: str) -> None:
    old_groups, new_groups = blocks(source), blocks(generated)
    if list(old_groups) != list(new_groups):
        raise ValueError("Generated overlay changed the group inventory/order")
    for name in old_groups:
        original, changed = old_groups[name][2], new_groups[name][2]
        _, _, original_names = contract_list(original)
        _, _, changed_names = contract_list(changed)
        if name in EXPECTED_GROUPS:
            if changed_names != original_names + [OBLIGATION]:
                raise ValueError(f"Obligation order/content changed unexpectedly: {name}")
            restored, count = re.subn(
                rf"(?m)^\t\t{OBLIGATION}\r?\n", "", changed
            )
            if count != 1 or restored != original:
                raise ValueError(f"Unexpected changes outside the appended obligation: {name}")
        elif changed != original:
            raise ValueError(f"Tributary group changed: {name}")
    # Also cover comments and whitespace between group definitions.
    restored = re.sub(rf"(?m)^\t\t{OBLIGATION}\r?\n", "", generated)
    if restored != source:
        raise ValueError("Overlay differs from vanilla beyond the 14 append-only additions")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify existing output without writing")
    args = parser.parse_args()
    try:
        upstream = (args.game_root / GROUP_PATH).read_bytes()
        expected = build(upstream)
        output = MOD_ROOT / GROUP_PATH
        if args.check:
            actual = output.read_bytes()
            verify_semantic_delta(upstream.decode("utf-8"), actual.decode("utf-8"))
            if actual != expected:
                raise ValueError("Overlay bytes do not match the deterministic build")
            print(f"PASS: pinned {UPSTREAM_VERSION}; 14 append-only vassal groups; tributaries unchanged")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(expected)
            print(f"Built {output}; 14 append-only vassal groups; tributaries unchanged")
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
