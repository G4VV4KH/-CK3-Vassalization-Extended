"""Render all supported CK3 localizations from the maintained language JSON files."""
from pathlib import Path
import argparse
import json

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('english', 'french', 'german', 'japanese', 'korean', 'polish', 'russian', 'simp_chinese', 'spanish')
PROFILES = ('low', 'default', 'high', 'religious')
CONCEPT_KEY = 'game_concept_vassalize_casus_belli_desc'


def load_language(language):
    data = json.loads((ROOT / 'tools/localization' / f'{language}.json').read_text(encoding='utf-8'))
    assert set(data) == {'names', 'strings', 'concept'}, f'{language}: invalid source sections'
    assert set(data['names']) == set(PROFILES), f'{language}: incomplete profile names'
    reference = json.loads((ROOT / 'tools/localization/english.json').read_text(encoding='utf-8'))
    assert set(data['strings']) == set(reference['strings']), f'{language}: incomplete strings'
    assert all(isinstance(v, str) and v.strip() for v in [*data['names'].values(), *data['strings'].values(), data['concept']])
    return data


def yaml(language, data):
    lines = [f'l_{language}:']
    for key, value in data.items():
        assert '"' not in value and '\r' not in value, f'{language}/{key}: unsupported quote/newline'
        lines.append(f' {key}:0 "' + value.replace('\n', '\\n') + '"')
    return '\n'.join(lines) + '\n'


def render(language):
    source = load_language(language)
    data = dict(source['strings'])
    for profile in PROFILES:
        name = source['names'][profile]
        data[f've_{profile}_cb_name'] = name
        cb_id = 'vassalization_cb' if profile == 'default' else f've_vassalization_{profile}_cb'
        if cb_id != 'vassalization_cb':
            data[cb_id] = name
            data[cb_id + '_desc'] = f'$ve_{profile}_cb_desc$'
        data[f've_{profile}_war_name'] = f'$VASSALIZATION_WAR_NAME$ — $ve_{profile}_cost_factor$'
        data[f've_{profile}_war_name_base'] = f'$VASSALIZATION_WAR_NAME_BASE$ — $ve_{profile}_cost_factor$'
    return yaml(language, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for language in LANGUAGES:
        outputs = {
            ROOT / 'localization' / language / f've_profiles_l_{language}.yml': render(language),
            ROOT / 'localization/replace' / f'vassalization_extended_l_{language}.yml': yaml(language, {CONCEPT_KEY: load_language(language)['concept']}),
        }
        for target, text in outputs.items():
            expected = text.encode('utf-8-sig')
            if args.check:
                assert target.read_bytes() == expected, f'Generated localization differs: {target}'
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(expected)
    print(f'All {len(LANGUAGES)} CK3 localizations ' + ('match source' if args.check else 'rendered'))


if __name__ == '__main__':
    main()
