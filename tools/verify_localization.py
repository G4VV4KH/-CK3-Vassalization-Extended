"""Validate complete CK3 language coverage and protected localization syntax.

This checks files and substitutions, not native UI layout or human playtesting.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('english', 'french', 'german', 'japanese', 'korean', 'polish', 'russian', 'simp_chinese', 'spanish')
LINE = re.compile(r'^ ([A-Za-z_0-9]+):0 "([^"\r\n]*)"$')
REF = re.compile(r'\$([A-Za-z_0-9]+)\$')
SCOPED = re.compile(r'\[(?:attacker|defender)\.[^\]]+\]')


def read_language(root, language):
    paths = sorted((root / 'localization').rglob(f'*_l_{language}.yml'))
    assert len(paths) == 2, f'{language}: expected profiles and concept override'
    entries = {}
    for path in paths:
        raw = path.read_bytes()
        assert raw.startswith(b'\xef\xbb\xbf'), f'{path}: missing UTF-8 BOM'
        lines = raw.decode('utf-8-sig').splitlines()
        assert lines[0] == f'l_{language}:', f'{path}: incorrect header'
        for line in lines[1:]:
            match = LINE.fullmatch(line)
            assert match, f'{path}: malformed localization line'
            key, value = match.groups()
            assert key not in entries, f'{language}: duplicate key {key}'
            assert value.strip(), f'{language}/{key}: empty value'
            assert value.count('[') == value.count(']'), f'{language}/{key}: unbalanced substitution'
            assert value.count('$') == 2 * len(REF.findall(value)), f'{language}/{key}: malformed reference'
            entries[key] = value
    return entries


def verify(root=ROOT, game_root=None):
    expected_files = {f'{language}/ve_profiles_l_{language}.yml' for language in LANGUAGES}
    expected_files |= {f'replace/vassalization_extended_l_{language}.yml' for language in LANGUAGES}
    actual_files = {p.relative_to(root / 'localization').as_posix() for p in (root / 'localization').rglob('*') if p.is_file()}
    assert actual_files == expected_files, 'Unexpected or missing localization file'
    if game_root:
        installed = {p.name for p in (game_root / 'localization').iterdir() if p.is_dir() and p.name != 'jomini'}
        assert installed == set(LANGUAGES), f'Installed CK3 language coverage changed: {installed}'
    languages = {language: read_language(root, language) for language in LANGUAGES}
    english = languages['english']
    scope_signatures = json.loads((ROOT / 'tools/localization/scope-signatures.json').read_text(encoding='utf-8'))['per_language']
    assert set(scope_signatures) == set(LANGUAGES), 'Reviewed scope signature language inventory differs'
    assert all(set(scope_signatures[l]) == set(languages[l]) for l in LANGUAGES), 'Reviewed scope signature key inventory differs'
    details = []
    for language, values in languages.items():
        assert values.keys() == english.keys(), f'{language}: key coverage differs'
        for key, text in values.items():
            reference = english[key]
            assert Counter(REF.findall(text)) == Counter(REF.findall(reference)), f'{language}/{key}: localization references changed'
            assert Counter(re.findall(r'\[[^\]]+\]', text)) == Counter(scope_signatures[language][key]), f'{language}/{key}: reviewed locale expression signatures changed'
            for ref in REF.findall(text):
                assert ref in values or ref in {'VASSALIZATION_WAR_NAME', 'VASSALIZATION_WAR_NAME_BASE'}, f'{language}/{key}: unresolved reference {ref}'
            # Decimal punctuation may be localized; numeric meaning must survive.
            numbers = lambda value: Counter(n.replace(',', '.') for n in re.findall(r'\d+(?:[.,]\d+)?', value))
            assert numbers(text) == numbers(reference), f'{language}/{key}: numeric mechanics changed'
            if key == 've_refusal_risk_desc':
                assert '[piety_level|E]' in text or "Concept('piety_level'," in text, f'{language}: missing devotion concept'
            if key == 'game_concept_vassalize_casus_belli_desc':
                assert "[GetPerk( 'forced_vassalage_perk' ).GetName( GetNullCharacter )]" in text, f'{language}: perk substitution changed'
            if language not in ('english', 'russian') and not REF.fullmatch(text) and '$VASSALIZATION_WAR_NAME' not in text:
                assert text != reference, f'{language}/{key}: untranslated English fallback'
        details.append({'language': language, 'keys': len(values), 'files': 2, 'complete': True})
    return {'status': 'LOCALIZATION_CHECKS_PASSED', 'languages': details, 'key_count_per_language': len(english), 'file_count': len(actual_files), 'checks': ['all installed CK3 languages', 'UTF-8 BOM, headers and line syntax', 'identical key sets without duplicates', 'localization and character substitutions', 'numeric mechanics', 'devotion and perk concepts', 'no English fallback in added languages'], 'engine_visual_test_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-root', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(game_root=args.game_root)
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(text, encoding='utf-8')
    print(text, end='')


if __name__ == '__main__':
    main()
