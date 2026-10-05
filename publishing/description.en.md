# Vassalization Extended

## At a glance

- 🟢 **Version 0.2.1** · Targets CK3 **1.20.0.3**.
- 🟢 **Standalone:** no additional mod required.
- 🟢 **Forced Vassalization has no target county limit.**
- 🟢 **Four peace terms in one expandable Vassalization group.**
- 🟢 All nine CK3 languages: **English, French, German, Japanese, Korean, Polish, Russian, Simplified Chinese and Spanish**.
- 🔴 Changes gameplay for **both players and AI**. Larger realms can be targeted when the other requirements are met.
- 🔴 Conflicts with replacements of the Forced Vassalization CB, Declare War window or subject contract groups.
- 🔴 Refusing available religious protection risks **one level of devotion** if the attacker loses.

## A kingdom can bend the knee

Bring a neighboring ruler into your realm without an arbitrary ceiling on the number of counties they govern. Choose the obligations and religious rights that their submission will secure before you declare war.

## Choose the terms of submission

Removes the county-count eligibility check from the existing **Forced Vassalization** casus belli. There is no replacement numeric cap.

The target must still be an independent neighboring ruler of lower rank. You still need access to the casus belli through the vanilla perk or another qualifying vanilla route. Existing restrictions on declaring war remain in place.

| Terms | Feudal taxes / levies, before modifiers | Prestige cost | Defeat reparations |
| --- | --- | --- | --- |
| Low obligations | 2.5% / 10% | 75% of ordinary | 75% of ordinary |
| Normal obligations | 10% / 25% | Ordinary | Ordinary |
| High obligations | 15% / 35% | 150% of ordinary | 150% of ordinary |
| Religious protection | 10% / 10%, with protection | 75% of ordinary | 75% of ordinary |

Non-feudal targets offer **Normal Obligations** and **Religious Protection**. Both keep their government's ordinary financial and military obligations; the protection option adds religious rights. The religious option remains visible but cannot be used to declare war when the vanilla conditions for granting religious protection are not met.

Prestige cost still scales with the target's counties and title rank before the selected terms modify it. Ordinary defeat reparations normally use three annual incomes of the attacker; special income and cultural rules still apply. Religious piety costs and the remaining victory, white-peace and defeat effects retain their vanilla rules.

Victory keeps the defeated ruler's titles and makes them a direct vassal. The chosen feudal obligations count as an agreed contract change, applying the ordinary restriction on another negotiation. Low/high-obligation wars invalidate if the target ceases to use a feudal government during the war.

## Religious protection and the cost of refusing it

Protection prevents the liege from demanding the vassal's conversion, using Convert Faith in County in protected lands, or using faith alone to avoid tyranny when revoking titles. It does **not** prevent every title revocation. The religious guarantee is a peace term and cannot be removed through ordinary contract negotiation; changing faith does not erase it.

Eligibility follows the vanilla religious-protection checkbox: the rulers must have different faiths, with the vanilla Jizya/nonbeliever-tax restriction and its existing-contract exception. This condition is checked when declaring war. If protection was available and the attacker chose another vassalization option, **attacker defeat costs one level of devotion**, in addition to normal consequences. The risk is inherited with the war and is not recalculated after a faith change. White peace does not incur this extra penalty.

Peaceful **Offer Vassalization** and **Swear Fealty** retain their existing conditions and acceptance scores.

## Getting started

1. Enable **Vassalization Extended** in your launcher playset.
2. Obtain access to Forced Vassalization and choose a neighboring independent ruler of lower rank.
3. Open **Declare War**, expand **Vassalization — choose the terms**, and select a profile.
4. Read its tooltip and victory/defeat preview, then review the price before declaring war.

## Compatibility and load order

Replaces `common/casus_belli_types/00_vassalization.txt`, `gui/interaction_declare_war.gui` and `common/subject_contracts/groups/subject_contract_groups.txt`. Adds a religious peace obligation to the vanilla vassal contract groups and overrides the Forced Vassalization concept description in all nine CK3 languages. Other mods changing these files, groups or descriptions need a compatibility review; load order alone cannot merge their changes.

No total-conversion compatibility is claimed. The mod adds no new DLC requirement; vanilla unlock routes retain their own requirements.

## Saves and known limits

The mod adds three CB IDs, war variables and a contract obligation. **Keep the mod enabled for campaigns using these wars or protected contracts.** Removing it or downgrading during such a campaign is unsupported. Back up your save before installing or updating the mod.

Wars already active under the original CB before this update retain their former resolution and do not acquire the new devotion penalty. Existing contract obligation order is preserved; the new religious peace term is appended. Total-conversion governments with custom contract groups need an adapter for religious protection.

Diplomatic acceptance is unchanged. AI can choose the new profiles with explicit personality preferences; the scripted Conqueror forced-war route continues to use ordinary vassalization. Some vanilla memory and war-message classifications recognize only the original CB and use generic text for new variants.

## Feedback and support

Include the CK3 version, mod list and load order, attacker and defender ranks, target realm size, unlock route and a screenshot of the unavailable casus belli or error.

[Report an issue on GitHub](https://github.com/G4VV4KH/-CK3-Vassalization-Extended/issues).

**Email:** g4vv4kh@gmail.com

### [Want to support my work? Donate on Ko-fi 💛](https://ko-fi.com/g4vv4kh)

## Find Vassalization Extended elsewhere

- [Steam Workshop](https://steamcommunity.com/sharedfiles/filedetails/?id=3813943691)
- [Paradox Mods](https://mods.paradoxplaza.com/mods/162059/Any)
- [Nexus Mods](https://www.nexusmods.com/crusaderkings3/mods/407)
- [GitHub source](https://github.com/G4VV4KH/-CK3-Vassalization-Extended)

## My mods

- [Parley: The Negotiating Table](https://steamcommunity.com/sharedfiles/filedetails/?id=3811090081) — negotiate complete diplomatic agreements.
- [Marriage Calculation Assistant](https://steamcommunity.com/sharedfiles/filedetails/?id=3811100163) — compare marriage candidates with readable scores and sorting.
- [Your Own Hegemony](https://steamcommunity.com/sharedfiles/filedetails/?id=3811201582) — unite imperial crowns under a new hegemony.

These mods are optional. [AGOT: Marriage Calculation Assistant](https://github.com/G4VV4KH/-CK3-AGOT-Marriage-Calculation-Assistant) remains on hold for CK3 1.20.

## Credits

The promotional cover is AI-generated artwork. Gallery images are authentic Crusader Kings III screenshots.
