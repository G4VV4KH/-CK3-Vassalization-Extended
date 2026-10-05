"""Render the English/Russian profile names and explanations as CK3 UTF-8-BOM YAML."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "english": {"low": "Vassalization: Low Obligations", "default": "Vassalization: Normal Obligations", "high": "Vassalization: High Obligations", "religious": "Vassalization: Religious Protection"},
    "russian": {"low": "Вассализация: низкие обязательства", "default": "Вассализация: обычные обязательства", "high": "Вассализация: высокие обязательства", "religious": "Вассализация: религиозная защита"},
}
EN = {
    "ve_vassalization_group_name": "Vassalization — choose the terms",
    "ve_vassalization_group_desc": "Expand to choose the future vassal's obligations and religious rights. Each option shows its prestige cost, victory terms and defeat consequences.",
    "ve_refusal_risk_desc": "If Religious Protection was available when this war was declared, losing without offering it also costs the attacker one [piety_level|E]. This risk is fixed at declaration and inherited with the war. White peace does not incur this penalty.",
    "ve_religious_protection_available_tt": "Religious Protection must be available under the vanilla contract conditions: different faiths and no Jizya/nonbeliever-tax restriction, except the vanilla exception for an already protected contract without title-revocation protection.",
    "ve_contract_lock_desc": "The feudal obligations count as an agreed contract change and receive the ordinary restriction on further negotiation.",
    "ve_protection_rights_desc": "The liege cannot demand the vassal's conversion, use Convert Faith in County in the protected lands, or use faith alone to avoid tyranny when revoking titles. This is not blanket protection from title revocation. The religious guarantee cannot be traded away in ordinary contract negotiations.",
    "ve_low_cb_desc": "Low feudal taxes (base 2.5%) and levies (10%). Prestige cost: 75% of ordinary vassalization. Defeat reparations: 75% of ordinary reparations.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_default_cb_desc": "Normal feudal taxes (base 10%) and levies (25%); other governments retain their ordinary obligations. Prestige cost and defeat reparations: ordinary vassalization rates.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_high_cb_desc": "High feudal taxes (base 15%) and levies (35%). Prestige cost: 150% of ordinary vassalization. Defeat reparations: 150% of ordinary reparations.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_religious_cb_desc": "Religious protection for any government. Feudal vassals pay normal taxes (base 10%) and low levies (10%); other governments keep ordinary obligations. Prestige cost and defeat reparations: 75% of ordinary rates. No devotion penalty for refusing protection.\n\n$ve_protection_rights_desc$\n\n$ve_contract_lock_desc$",
    "ve_low_victory_desc": "[defender.GetShortUIName|U] becomes a direct vassal of [attacker.GetShortUIName], retaining their titles, with low feudal taxes and levies. Base rates: 2.5% tax / 10% levies. $ve_contract_lock_desc$",
    "ve_default_victory_desc": "[defender.GetShortUIName|U] becomes a direct vassal of [attacker.GetShortUIName], retaining their titles. Feudal contracts receive normal obligations (base 10% tax / 25% levies); other governments retain ordinary obligations. $ve_contract_lock_desc$",
    "ve_high_victory_desc": "[defender.GetShortUIName|U] becomes a direct vassal of [attacker.GetShortUIName], retaining their titles, with high feudal taxes and levies. Base rates: 15% tax / 35% levies. $ve_contract_lock_desc$",
    "ve_religious_victory_desc": "[defender.GetShortUIName|U] becomes a direct vassal of [attacker.GetShortUIName], retaining their titles and receiving religious protection. Feudal contracts receive normal taxes and low levies (base 10% / 10%); other governments retain ordinary obligations.\n\n$ve_protection_rights_desc$\n\n$ve_contract_lock_desc$",
    "ve_low_defeat_desc": "[defender.GetShortUIName|U] remains independent. [attacker.GetShortUIName|U] pays 75% of ordinary vassalization reparations (normally 2.25 annual incomes, before special modifiers) and suffers the ordinary defeat effects.\n\n$ve_refusal_risk_desc$",
    "ve_default_defeat_desc": "[defender.GetShortUIName|U] remains independent. [attacker.GetShortUIName|U] pays ordinary vassalization reparations (normally 3 annual incomes, before special modifiers) and suffers the ordinary defeat effects.\n\n$ve_refusal_risk_desc$",
    "ve_high_defeat_desc": "[defender.GetShortUIName|U] remains independent. [attacker.GetShortUIName|U] pays 150% of ordinary vassalization reparations (normally 4.5 annual incomes, before special modifiers) and suffers the ordinary defeat effects.\n\n$ve_refusal_risk_desc$",
    "ve_religious_defeat_desc": "[defender.GetShortUIName|U] remains independent. [attacker.GetShortUIName|U] pays 75% of ordinary vassalization reparations (normally 2.25 annual incomes, before special modifiers) and suffers the ordinary defeat effects. This CB incurs no devotion penalty for refusing religious protection.",
    "ve_default_cost_factor": "Normal obligations",
    "ve_low_cost_factor": "Low obligations",
    "ve_high_cost_factor": "High obligations",
    "ve_religious_cost_factor": "Religious protection",
    "ve_religious_protection": "Religious protection secured by peace",
    "ve_religious_protection_none": "No peace guarantee",
    "ve_religious_protection_none_short": "Not guaranteed",
    "ve_religious_protection_none_desc": "This contract has no religious guarantee imposed by a Vassalization Extended peace settlement.",
    "ve_religious_protection_protected": "Religious protection secured by peace",
    "ve_religious_protection_protected_short": "Protected by peace",
    "ve_religious_protection_protected_desc": "$ve_protection_rights_desc$",
}
RU = {
    "ve_vassalization_group_name": "Вассализация — выбор условий",
    "ve_vassalization_group_desc": "Разверните группу, чтобы выбрать обязательства и религиозные права будущего вассала. У каждого варианта указаны цена в престиже, условия победы и последствия поражения.",
    "ve_refusal_risk_desc": "Если при объявлении войны была доступна религиозная защита, поражение при выборе другого варианта дополнительно отнимет у нападающего один [Concept('piety_level', 'уровень набожности')|E]. Этот риск фиксируется при объявлении и наследуется вместе с войной. При белом мире штрафа нет.",
    "ve_religious_protection_available_tt": "Религиозная защита должна быть доступна по условиям ванильного договора: разные конфессии и отсутствие ограничения джизьи/налога на иноверцев, кроме ванильного исключения для уже защищённого договора без защиты от отзыва титулов.",
    "ve_contract_lock_desc": "Феодальные обязательства считаются согласованным изменением договора: на дальнейший пересмотр действует обычное ограничение переговоров.",
    "ve_protection_rights_desc": "Сюзерен не может требовать обращения вассала, обращать графства защищённых земель и использовать различие веры как основание для отзыва титулов без тирании. Это не полный запрет отзыва титулов. Религиозную гарантию нельзя отменить обычным пересмотром договора.",
    "ve_low_cb_desc": "Низкие феодальные налоги (база 2,5%) и ополчение (10%). Цена в престиже: 75% обычной вассализации. Контрибуция при поражении: 75% обычной.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_default_cb_desc": "Обычные феодальные налоги (база 10%) и ополчение (25%); при других формах правления сохраняются обычные обязательства. Цена в престиже и контрибуция — как при обычной вассализации.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_high_cb_desc": "Высокие феодальные налоги (база 15%) и ополчение (35%). Цена в престиже: 150% обычной вассализации. Контрибуция при поражении: 150% обычной.\n\n$ve_contract_lock_desc$\n\n$ve_refusal_risk_desc$",
    "ve_religious_cb_desc": "Религиозная защита при любой форме правления. У феодалов — обычные налоги (база 10%) и низкое ополчение (10%); у остальных — обычные обязательства. Цена в престиже и контрибуция: 75% обычных. Штрафа к набожности за отказ от защиты нет.\n\n$ve_protection_rights_desc$\n\n$ve_contract_lock_desc$",
    "ve_low_victory_desc": "[defender.GetShortUIName|U] становится прямым вассалом [attacker.GetShortUIName], сохраняя титулы, с низкими феодальными налогами и ополчением. Базовые ставки: 2,5% налогов / 10% ополчения. $ve_contract_lock_desc$",
    "ve_default_victory_desc": "[defender.GetShortUIName|U] становится прямым вассалом [attacker.GetShortUIName], сохраняя титулы. У феодалов — обычные обязательства (база 10% налогов / 25% ополчения); у остальных — обычные обязательства их формы правления. $ve_contract_lock_desc$",
    "ve_high_victory_desc": "[defender.GetShortUIName|U] становится прямым вассалом [attacker.GetShortUIName], сохраняя титулы, с высокими феодальными налогами и ополчением. Базовые ставки: 15% налогов / 35% ополчения. $ve_contract_lock_desc$",
    "ve_religious_victory_desc": "[defender.GetShortUIName|U] становится прямым вассалом [attacker.GetShortUIName], сохраняя титулы и получая религиозную защиту. У феодалов — обычные налоги и низкое ополчение (база 10% / 10%); у остальных — обычные обязательства их формы правления.\n\n$ve_protection_rights_desc$\n\n$ve_contract_lock_desc$",
    "ve_low_defeat_desc": "[defender.GetShortUIName|U] остаётся независимым правителем. [attacker.GetShortUIName|U] платит 75% обычной контрибуции за вассализацию (как правило, 2,25 годовых дохода до особых модификаторов) и несёт обычные последствия поражения.\n\n$ve_refusal_risk_desc$",
    "ve_default_defeat_desc": "[defender.GetShortUIName|U] остаётся независимым правителем. [attacker.GetShortUIName|U] платит обычную контрибуцию за вассализацию (как правило, 3 годовых дохода до особых модификаторов) и несёт обычные последствия поражения.\n\n$ve_refusal_risk_desc$",
    "ve_high_defeat_desc": "[defender.GetShortUIName|U] остаётся независимым правителем. [attacker.GetShortUIName|U] платит 150% обычной контрибуции за вассализацию (как правило, 4,5 годовых дохода до особых модификаторов) и несёт обычные последствия поражения.\n\n$ve_refusal_risk_desc$",
    "ve_religious_defeat_desc": "[defender.GetShortUIName|U] остаётся независимым правителем. [attacker.GetShortUIName|U] платит 75% обычной контрибуции за вассализацию (как правило, 2,25 годовых дохода до особых модификаторов) и несёт обычные последствия поражения. Этот CB не штрафует набожность за отказ от религиозной защиты.",
    "ve_default_cost_factor": "Обычные обязательства",
    "ve_low_cost_factor": "Низкие обязательства",
    "ve_high_cost_factor": "Высокие обязательства",
    "ve_religious_cost_factor": "Религиозная защита",
    "ve_religious_protection": "Религиозная защита по условиям мира",
    "ve_religious_protection_none": "Нет гарантии по условиям мира",
    "ve_religious_protection_none_short": "Нет гарантии",
    "ve_religious_protection_none_desc": "Этот договор не содержит религиозной гарантии по условиям мира Vassalization Extended.",
    "ve_religious_protection_protected": "Религиозная защита по условиям мира",
    "ve_religious_protection_protected_short": "Защищено договором",
    "ve_religious_protection_protected_desc": "$ve_protection_rights_desc$",
}


def render(language):
    data = dict(EN if language == "english" else RU)
    for profile, name in NAMES[language].items():
        data[f"ve_{profile}_cb_name"] = name
        cb_id = "vassalization_cb" if profile == "default" else f"ve_vassalization_{profile}_cb"
        # Database type names are distinct from cb_name; keep both meaningful.
        if cb_id != "vassalization_cb":
            data[cb_id] = name
            data[cb_id + "_desc"] = f"$ve_{profile}_cb_desc$"
        data[f"ve_{profile}_war_name"] = f"$VASSALIZATION_WAR_NAME$ — $ve_{profile}_cost_factor$"
        data[f"ve_{profile}_war_name_base"] = f"$VASSALIZATION_WAR_NAME_BASE$ — $ve_{profile}_cost_factor$"
    for value in data.values():
        assert '"' not in value, "Use typographic quotes inside localization"
    lines = [f"l_{language}:"]
    for key, value in data.items():
        lines.append(f' {key}:0 "' + value.replace("\n", "\\n") + '"')
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    assert set(EN) == set(RU)
    for language in NAMES:
        target = ROOT / "localization" / language / f"ve_profiles_l_{language}.yml"
        text = render(language)
        if args.check:
            assert target.read_text(encoding="utf-8-sig") == text
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8-sig", newline="\n")
    print("Profile localization matches source" if args.check else "Rendered English and Russian profile localization")


if __name__ == "__main__":
    main()
