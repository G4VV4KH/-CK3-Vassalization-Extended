"""Independent static regression checks for the four CB profiles, not an engine test.

Run with --game-root pointing to CK3/game. Reports go to stdout unless an explicit
--report path is supplied. This verifier never installs a mod or changes a save.
"""
from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from verify_source import TOKEN, parse, sha

ROOT = Path(__file__).resolve().parents[1]
CB_PATH = Path("common/casus_belli_types/00_vassalization.txt")
GUI_PATH = Path("gui/interaction_declare_war.gui")
GUI_UPSTREAM_SHA256 = "b0703faef1b1162e3a41d6de3fc6415ad5f1cb23edbd353e1526d7ac54b9d527"
PROFILES = {
    "vassalization_cb": ("default", Decimal("1"), Decimal("3")),
    "ve_vassalization_low_cb": ("low", Decimal("0.75"), Decimal("2.25")),
    "ve_vassalization_high_cb": ("high", Decimal("1.5"), Decimal("4.5")),
    "ve_vassalization_religious_cb": ("religious", Decimal("0.75"), Decimal("2.25")),
}


def entries(node, name):
    return [value for key, op, value in node if key == name]


def one(node, name):
    found = entries(node, name)
    assert len(found) == 1, f"{name}: expected exactly one entry, got {len(found)}"
    return found[0]


def descendants(node, name):
    result = []
    for key, op, value in node:
        if key == name:
            result.append(value)
        if isinstance(value, list):
            result.extend(descendants(value, name))
    return result


def numeric(token):
    return Decimal(token.strip('"'))


def lexical_tokens(text):
    """Tokenize GUI syntax and check balanced braces without inventing a GUI parser."""
    result, end, depth = [], 0, 0
    for match in TOKEN.finditer(text):
        assert match.start() == end, f"Unrecognized input at {end}"
        end = match.end()
        token = match.group()
        if token.isspace() or token.startswith("#"):
            continue
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            assert depth >= 0, "Unmatched closing brace"
        result.append(token)
    assert end == len(text), "Unrecognized trailing input"
    assert depth == 0, "Unclosed GUI block"
    return result


def named_block(text, name):
    """Extract one named block without assuming its children are assignments."""
    start = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*\{", text)
    assert start, name
    depth = 1
    for token in TOKEN.finditer(text, start.end()):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return text[start.end():token.start()]
    raise AssertionError("Unclosed " + name)


def remove_one(node, name):
    one(node, name)
    return [entry for entry in node if entry[0] != name]


def writes(node, ancestors=()):
    for key, op, value in node:
        if key == "set_variable":
            yield ancestors, value
        if isinstance(value, list):
            yield from writes(value, ancestors + (key,))


def validate_religious_write_permission(effects, contract_text):
    """Regression for native setters honoring both obligation visibility and change gates."""
    contract = named_block(contract_text, "ve_religious_protection")
    permission = parse(named_block(contract, "can_be_changed"))
    assert permission == parse("scope:subject = { has_character_flag = ve_granting_religious_protection }"), "Contract must grant write permission only to the flagged subject"
    shown = parse(named_block(contract, "is_shown"))
    assert shown == parse("""
        scope:subject = {
            OR = {
                has_character_flag = ve_granting_religious_protection
                vassal_contract_obligation_level:ve_religious_protection = 1
            }
        }
    """), "Contract must be visible during the temporary write and remain visible after protection is granted"
    apply = one(one(effects, "ve_apply_vassalization_terms_effect"), "hidden_effect")
    subject = one(one(apply, "if"), "scope:defender")
    religious = entries(subject, "if")[1]
    assert religious == parse("""
        limit = { always = $RELIGIOUS_PROTECTION$ }
        add_character_flag = ve_granting_religious_protection
        vassal_contract_set_obligation_level = { type = ve_religious_protection level = 1 }
        remove_character_flag = ve_granting_religious_protection
    """), "Permission must open, write level 1 and close immediately, only in the religious branch on the defender"
    assert descendants(effects, "add_character_flag") == ["ve_granting_religious_protection"], "Unexpected extra permission writer"
    assert descendants(effects, "remove_character_flag") == ["ve_granting_religious_protection"], "Unexpected extra permission cleanup"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    passed, failures = [], []

    def check(label, action):
        try:
            action()
        except (AssertionError, ValueError, KeyError, TypeError, IndexError) as error:
            failures.append({"check": label, "error": str(error)})
        else:
            passed.append(label)

    def require(condition, message):
        assert condition, message

    upstream_raw = (args.game_root / CB_PATH).read_bytes()
    mod_raw = (ROOT / CB_PATH).read_bytes()
    recorded = json.loads((ROOT / "docs/upstream.json").read_text(encoding="utf-8"))
    check("upstream fingerprint", lambda: require(
        sha(upstream_raw) == recorded["cb_sha256"], "Installed vanilla CB differs from the pinned source"))
    vanilla = one(parse(upstream_raw.decode("utf-8-sig")), "vassalization_cb")
    mod = parse(mod_raw.decode("utf-8-sig"))
    check("exactly four stable CB IDs", lambda: require(
        sorted(key for key, op, value in mod) == sorted(PROFILES),
        "Missing, duplicate, or unexpected CB definitions"))

    # These are the reviewed extension points. Everything else must retain the
    # engine's complete current vanilla subtree, including AI and succession.
    mutable = {
        "allowed_against_character_display_regardless", "allowed_against_character",
        "should_invalidate", "cost", "on_declaration", "on_victory", "on_defeat",
        "cb_name", "war_name", "war_name_base", "interface_priority",
        "on_victory_desc", "on_defeat_desc", "ai_score_mult",
    }
    immutable = [entry for entry in vanilla if entry[0] not in mutable]
    for cb_id, (profile, cost_multiplier, reparations) in PROFILES.items():
        if len(entries(mod, cb_id)) != 1:
            continue
        cb = one(mod, cb_id)
        check(f"{profile}: unrelated vanilla behavior retained", lambda cb=cb: require(
            [entry for entry in cb if entry[0] not in mutable] == immutable,
            "A vanilla subtree outside the reviewed extension points changed"))
        check(f"{profile}: no county cap", lambda cb=cb: require(
            not descendants(cb, "count") or all(
                value != "vassalization_size_limit" for value in descendants(cb, "count")),
            "Target county limit remains in this profile"))
        check(f"{profile}: piety cost retained", lambda cb=cb: require(
            entries(one(cb, "cost"), "piety") == entries(one(vanilla, "cost"), "piety"),
            "Vanilla piety cost changed"))

        def check_prestige(cb=cb, multiplier=cost_multiplier):
            original = one(one(vanilla, "cost"), "prestige")
            current = one(one(cb, "cost"), "prestige")
            if multiplier == 1 and current == original:
                return
            assert current[:len(original)] == original, "Original prestige calculation was altered"
            extra = current[len(original):]
            assert len(extra) == 1 and extra[0][:2] == ("multiply", "="), extra
            value = extra[0][2]
            if isinstance(value, list):
                value = one(value, "value")
            assert numeric(value) == multiplier, f"Expected prestige multiplier {multiplier}, got {value}"
        check(f"{profile}: prestige multiplier", check_prestige)

        def check_reparations(cb=cb, amount=reparations):
            payments = descendants(one(cb, "on_defeat"), "pay_short_term_gold_reparations_effect")
            assert len(payments) == 1, f"Expected one defeat payment, got {len(payments)}"
            assert numeric(one(payments[0], "GOLD_VALUE")) == amount
        check(f"{profile}: defeat reparations", check_reparations)

        def check_gates(cb=cb, profile=profile):
            expected_display = deepcopy(one(vanilla, "allowed_against_character_display_regardless"))
            expected_display = remove_one(expected_display, "scope:defender")
            if profile == "religious":
                expected_display += parse("""custom_description = {
                    text = ve_religious_protection_available_tt
                    ve_religious_protection_available_trigger = yes
                }""")
            assert one(cb, "allowed_against_character_display_regardless") == expected_display
            expected_against = deepcopy(one(vanilla, "allowed_against_character"))
            expected_invalidation = deepcopy(one(vanilla, "should_invalidate"))
            if profile in {"low", "high"}:
                expected_against += parse("scope:defender = { ve_uses_feudal_obligations_trigger = yes }")
                current_invalidation = deepcopy(one(cb, "should_invalidate"))
                alternatives = one(current_invalidation, "OR")
                addition = ("scope:defender", "=", [("ve_uses_feudal_obligations_trigger", "=", "no")])
                assert alternatives.count(addition) == 1
                alternatives.remove(addition)
                assert current_invalidation == expected_invalidation
            else:
                assert one(cb, "should_invalidate") == expected_invalidation
            assert one(cb, "allowed_against_character") == expected_against
        check(f"{profile}: every remaining vanilla gate retained", check_gates)

        def check_effects(cb=cb, profile=profile):
            declaration = one(cb, "on_declaration")
            hook = one(declaration, "ve_record_vassalization_terms_effect")
            assert one(hook, "PROFILE") == profile
            assert one(hook, "REFUSAL_RISK") == ("no" if profile == "religious" else "yes")
            assert remove_one(declaration, "ve_record_vassalization_terms_effect") == one(vanilla, "on_declaration")
            victory = one(cb, "on_victory")
            terms = one(victory, "ve_apply_vassalization_terms_effect")
            levels = {"low": ("1", "1"), "default": ("2", "2"), "high": ("3", "3"), "religious": ("2", "1")}
            assert (one(terms, "TAX_LEVEL"), one(terms, "LEVY_LEVEL")) == levels[profile]
            assert one(terms, "RELIGIOUS_PROTECTION") == ("yes" if profile == "religious" else "no")
            assert remove_one(victory, "ve_apply_vassalization_terms_effect") == one(vanilla, "on_victory")
            apply_index = next(i for i, entry in enumerate(victory) if entry[0] == "ve_apply_vassalization_terms_effect")
            assert any(descendants([entry], "resolve_title_and_vassal_change") for entry in victory[:apply_index]), "Contract applied before the new liege resolves"
            defeat = deepcopy(one(cb, "on_defeat"))
            if profile != "religious":
                assert one(defeat, "ve_apply_refusal_devotion_penalty_effect") == "yes"
                defeat = remove_one(defeat, "ve_apply_refusal_devotion_penalty_effect")
            else:
                assert not descendants(defeat, "ve_apply_refusal_devotion_penalty_effect")
            payment = descendants(defeat, "pay_short_term_gold_reparations_effect")[0]
            payment[:] = [(key, op, "3" if key == "GOLD_VALUE" else value) for key, op, value in payment]
            assert defeat == one(vanilla, "on_defeat"), "Other vanilla defeat effects changed"
            for outcome in ("on_white_peace", "on_invalidated"):
                assert not descendants(one(cb, outcome), "ve_apply_refusal_devotion_penalty_effect")
            assert one(cb, "ai_score_mult") == one(vanilla, "ai_score_mult") + [("multiply", "=", f"ve_{profile}_ai_weight")]
        check(f"{profile}: outcome hooks retain vanilla effects and order", check_effects)

    effects = parse((ROOT / "common/scripted_effects/ve_vassalization_effects.txt").read_text(encoding="utf-8-sig"))
    triggers = parse((ROOT / "common/scripted_triggers/ve_vassalization_triggers.txt").read_text(encoding="utf-8-sig"))

    def check_snapshot():
        record = one(effects, "ve_record_vassalization_terms_effect")
        all_writes = list(writes(record))
        assert {one(value, "name") for path, value in all_writes} == {"ve_contract_profile", "ve_refused_religious_protection"}
        assert all("scope:war" in path for path, value in all_writes), "Terms must be stored on the war, not a character"
        assert next(one(value, "value") for path, value in all_writes if one(value, "name") == "ve_contract_profile") == "flag:$PROFILE$"
        risk = one(record, "if")
        assert one(risk, "limit") == parse("always = $REFUSAL_RISK$ ve_religious_protection_available_trigger = yes")
        trigger = one(triggers, "ve_refusal_devotion_penalty_trigger")
        real_war = one(trigger, "trigger_if")
        assert one(real_war, "limit") == parse("exists = scope:war")
        assert one(real_war, "scope:war") == parse("has_variable = ve_refused_religious_protection")
        assert not descendants(real_war, "ve_religious_protection_available_trigger"), "Actual wars must never reevaluate present-day religious eligibility"
        assert one(trigger, "trigger_else") == parse("ve_religious_protection_available_trigger = yes")
        penalty = one(effects, "ve_apply_refusal_devotion_penalty_effect")
        branch = one(penalty, "if")
        assert one(branch, "limit") == parse("ve_refusal_devotion_penalty_trigger = yes")
        assert one(branch, "scope:attacker") == parse("add_piety_level = -1"), "Must subtract one devotion level, not spendable piety"
    check("declaration snapshot; legacy wars and changed faith cannot alter the penalty", check_snapshot)

    def check_religion():
        contracts = (args.game_root / "common/subject_contracts/contracts/special_contracts.txt").read_text(encoding="utf-8-sig")
        religious = named_block(contracts, "religious_rights")
        protected = named_block(religious, "religious_rights_protected")
        validity = named_block(protected, "is_valid")
        expected = parse(validity.replace("scope:subject", "scope:defender").replace("scope:liege", "scope:attacker"))
        branch = one(one(expected, "OR"), "scope:defender")
        branch.insert(0, ("exists", "=", "liege"))
        assert one(triggers, "ve_religious_protection_available_trigger") == expected, "Eligibility diverges from current vanilla religious_rights, except the independent-defender guard"
        assert one(triggers, "ve_uses_feudal_obligations_trigger") == parse("OR = { government_has_flag = government_is_feudal government_has_flag = government_is_japan_feudal }")
    check("religious eligibility matches vanilla checkbox, Jizya and grandfather exception", check_religion)

    def check_contract_application():
        apply = one(one(effects, "ve_apply_vassalization_terms_effect"), "hidden_effect")
        branch = one(apply, "if")
        assert one(branch, "limit") == parse("exists = scope:war scope:war = { has_variable = ve_contract_profile } scope:defender = { liege = scope:attacker }")
        subject = one(branch, "scope:defender")
        feudal, religious = entries(subject, "if")
        assert one(feudal, "limit") == parse("OR = { has_subject_contract_group = feudal_vassal has_subject_contract_group = japan_feudal_vassal }")
        assert entries(feudal, "vassal_contract_set_obligation_level") == [
            parse("type = feudal_government_taxes level = $TAX_LEVEL$"),
            parse("type = feudal_government_levies level = $LEVY_LEVEL$"),
        ], "Non-feudal subjects must not receive feudal obligation effects"
        assert one(feudal, "set_subject_contract_modification_blocked") == "yes"
        assert one(religious, "limit") == parse("always = $RELIGIOUS_PROTECTION$")
        assert one(religious, "vassal_contract_set_obligation_level") == parse("type = ve_religious_protection level = 1")
    check("contract application is after victory, guarded for old wars and non-feudal governments", check_contract_application)

    def check_religious_permission():
        contract_path = ROOT / "common/subject_contracts/contracts/ve_religious_protection.txt"
        validate_religious_write_permission(effects, contract_path.read_text(encoding="utf-8-sig"))
        # No other script may open the same permission for ordinary negotiations.
        flag_uses = {}
        for path in (ROOT / "common").rglob("*.txt"):
            count = lexical_tokens(path.read_text(encoding="utf-8-sig")).count("ve_granting_religious_protection")
            if count:
                flag_uses[path.relative_to(ROOT).as_posix()] = count
        assert flag_uses == {
            "common/scripted_effects/ve_vassalization_effects.txt": 2,
            "common/subject_contracts/contracts/ve_religious_protection.txt": 2,
        }, "Religious write permission leaked outside the synchronous settlement helper and contract guard"
    check("religious contract change and visibility gates permit only the temporary subject-scoped write, with immediate cleanup", check_religious_permission)

    def check_localization():
        inventories = []
        for language in ("english", "russian"):
            keys = set()
            for path in (ROOT / "localization").rglob(f"*_l_{language}.yml"):
                raw = path.read_bytes()
                assert raw.startswith(b"\xef\xbb\xbf"), str(path)
                text = raw.decode("utf-8-sig")
                assert text.startswith(f"l_{language}:"), str(path)
                for match in re.finditer(r'^\s+([A-Za-z_0-9]+):\d*\s+"', text, re.M):
                    assert match[1] not in keys, f"Duplicate {language} key: {match[1]}"
                    keys.add(match[1])
            required = {f"ve_{profile}_{suffix}" for profile, _, _ in PROFILES.values() for suffix in ("cb_name", "war_name", "war_name_base", "victory_desc", "defeat_desc", "cost_factor")}
            assert required <= keys, f"Missing {language} keys: {sorted(required - keys)}"
            inventories.append(keys)
        assert inventories[0] == inventories[1], "English and Russian key sets differ"
        gui = (ROOT / "gui/interaction_declare_war.gui").read_text(encoding="utf-8-sig")
        for cb_id in PROFILES:
            assert f"GetCasusBelliType('{cb_id}')" in gui, f"GUI does not reference {cb_id}"
    check("English/Russian localization and native GUI reference every profile", check_localization)

    gui_upstream_raw = (args.game_root / GUI_PATH).read_bytes()
    gui_mod_raw = (ROOT / GUI_PATH).read_bytes()

    def check_gui_remainder():
        assert sha(gui_upstream_raw) == GUI_UPSTREAM_SHA256, "Vanilla GUI changed; review and rebase before updating the pin"
        vanilla_gui = gui_upstream_raw.decode("utf-8-sig")
        mod_gui = gui_mod_raw.decode("utf-8-sig")
        lexical_tokens(mod_gui)
        # Restore the native list entry after removing only the two marked extensions.
        vanilla_list = vanilla_gui[vanilla_gui.index('name = "casus_belli_items"'):]
        original_button = named_block(vanilla_list, "button_standard")
        list_match = re.search(r"(?ms)^\s*# VE_GROUP_LIST_BEGIN.*?^\s*# VE_GROUP_LIST_END[^\r\n]*", mod_gui)
        assert list_match, "Missing marked GUI list adapter"
        adapted_button = named_block(list_match.group(), "button_standard")
        button_without_filter, count = re.subn(
            r'(?m)^\s*visible = "\[Not\(ObjectsEqual\(CasusBelliItem.GetType, GetCasusBelliType\(\'vassalization_cb\'\)\)\)\]"\s*$',
            "", adapted_button,
        )
        assert count == 1, "Other CB buttons must have exactly one new group exclusion"
        assert lexical_tokens(button_without_filter) == lexical_tokens(original_button), "Other CB buttons lost native behavior"
        restored = mod_gui[:list_match.start()] + "\nbutton_standard = {" + original_button + "}\n" + mod_gui[list_match.end():]
        restored, count = re.subn(r"(?ms)^\s*# VE_GROUP_TYPES_BEGIN.*?^\s*# VE_GROUP_TYPES_END[^\r\n]*", "", restored)
        assert count == 1, "Expected one custom GUI types block"
        assert lexical_tokens(restored) == lexical_tokens(vanilla_gui), "Unrelated vanilla declare-war GUI changed"
    check("pinned vanilla GUI restored by subtracting the two marked adapters; native other-CB buttons retained", check_gui_remainder)

    descriptor = (ROOT / "descriptor.mod").read_text(encoding="utf-8-sig")
    check("descriptor does not replace whole vanilla directories", lambda: require(
        "replace_path" not in descriptor, "Unexpected replace_path"))
    runtime_paths = [ROOT / "descriptor.mod"] + sorted(
        path for folder in ("common", "gui", "localization")
        for path in (ROOT / folder).rglob("*") if path.is_file()
    )
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "status": "STATIC_CHECKS_PASSED" if not failures else "STATIC_CHECKS_FAILED",
        "game_version": recorded["game_version"],
        "upstream_sha256": sha(upstream_raw),
        "mod_cb_sha256": sha(mod_raw),
        "gui_upstream_sha256": sha(gui_upstream_raw),
        "gui_mod_sha256": sha(gui_mod_raw),
        "runtime_file_counts": {"gameplay_and_localization": len(runtime_paths) - 1, "source_descriptor": 1},
        "runtime_files": [
            {"path": path.relative_to(ROOT).as_posix(), "role": "source_descriptor" if path.name == "descriptor.mod" else "gameplay_or_localization", "bytes": path.stat().st_size, "sha256": sha(path.read_bytes())}
            for path in runtime_paths
        ],
        "checks_passed": passed,
        "failures": failures,
        "engine_test_performed": False,
        "limitations": "Static checks do not establish GUI behavior, engine effect semantics, AI choices, or save compatibility. Earlier static passes did not detect that can_be_changed and is_shown also affect scripted obligation setters; the regression records subsequent native findings without replacing native outcome tests.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    raise SystemExit(bool(failures))


if __name__ == "__main__":
    main()
