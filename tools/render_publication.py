"""Render this mod's canonical copy without touching runtime or sibling mods.

Usage: python tools/render_publication.py --output-dir /path/to/staging --build-id ID [--candidate rc2|release] [--launcher-wrapper NAME.mod]
The output directory is explicit; the canonical input is relative to this script.
Platform size checks use the project's current publishing profile, not a live form.
Candidate defaults to rc1. INSTALL and testing guides are generated with its identity.
The release profile emits public installation instructions and a gallery README.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BB_TAG = re.compile(r"\[/?(?:h[1-6]|b|size(?:=\d+)?|list(?:=1)?|olist)\]|\[\*\]")
TITLE = "Vassalization Extended"
GAME_TARGET = "1.20.0.3"
DONATION_TEXT = "Want to support my work? Donate on Ko-fi 💛"
DONATION_URL = "https://ko-fi.com/g4vv4kh"
DONATION_LINE = f"[{DONATION_TEXT}]({DONATION_URL})"
RELATED_MODS = {
    "Parley: The Negotiating Table": "https://steamcommunity.com/sharedfiles/filedetails/?id=3811090081",
    "Marriage Calculation Assistant": "https://steamcommunity.com/sharedfiles/filedetails/?id=3811100163",
    "Your Own Hegemony": "https://steamcommunity.com/sharedfiles/filedetails/?id=3811201582",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def platform_urls(source: str) -> dict[str, str]:
    """Use only links explicitly assigned in the canonical platform section."""
    section = re.search(r"(?ms)^## Find Vassalization Extended elsewhere\s*\n(.*?)(?=^## |\Z)", source)
    domains = {"github.com": "github", "steamcommunity.com": "steam", "mods.paradoxplaza.com": "paradox", "nexusmods.com": "nexus"}
    result = {}
    if section:
        for _, url in LINK.findall(section[1]):
            platform = domains.get((urlparse(url).hostname or "").removeprefix("www."))
            if platform:
                result[platform] = url
    return result


def platform_source(source: str, platform: str) -> str:
    """All platforms retain the owner's approved linked support wording."""
    return source


def unformat_bbcode(text: str) -> str:
    text = re.sub(r"\[url=([^\]]+)\](.*?)\[/url\]", lambda m: f"{m[2]}: {m[1]}", text)
    return BB_TAG.sub("", text)


def validate_support_and_catalog(text: str, platform: str, markup: str) -> list[dict]:
    """Required support and catalogue slots must survive every presentation."""
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append({"name": platform + ": " + name, "passed": bool(ok)})
        if not ok:
            raise ValueError(f"Publication validation failed: {platform}: {name}")

    visible = plain(text) if markup == "markdown" else unformat_bbcode(text) if markup == "bbcode" else text

    def section(start: str, end: str) -> str:
        match = re.search(r"(?ms)^" + re.escape(start) + r"\s*\n(.*?)(?=^" + re.escape(end) + r"\s*\n|\Z)", visible)
        return match[1] if match else ""

    def linked_pairs(start: str, end: str) -> list[tuple[str, str]]:
        lines = text.splitlines()
        labels = [plain(line).strip() if markup == "markdown" else unformat_bbcode(line).strip() for line in lines]
        if start not in labels or end not in labels:
            return []
        body = "\n".join(lines[labels.index(start) + 1:labels.index(end)])
        if markup == "markdown":
            return LINK.findall(body)
        return [(label, url) for url, label in re.findall(r"\[url=([^\]]+)\](.*?)\[/url\]", body)]

    support = section("Feedback and support", "Find Vassalization Extended elsewhere")
    expected = plain(DONATION_LINE).strip()
    check("required_support_text_and_url", expected in support and visible.count(DONATION_URL) == 1)
    if markup != "plain":
        check("support_clickable_link", (DONATION_TEXT, DONATION_URL) in linked_pairs("Feedback and support", "Find Vassalization Extended elsewhere"))
    catalog = section("My mods", "Credits")
    check("populated_my_mods", all(any(name in line and url in line and " — " in line and line.rsplit(" — ", 1)[-1].strip() for line in catalog.splitlines()) for name, url in RELATED_MODS.items()))
    if markup != "plain":
        check("my_mods_clickable_links", all(pair in linked_pairs("My mods", "Credits") for pair in RELATED_MODS.items()))
    check("my_mods_after_platforms", visible.find("\nFind Vassalization Extended elsewhere\n") < visible.find("\nMy mods\n") < visible.find("\nCredits\n"))
    if "AGOT:" in catalog:
        check("agot_hold_preserved", any("AGOT:" in line and "on hold" in line for line in catalog.splitlines()))
    return checks


def flatten_tables(text: str) -> str:
    out = []
    header = None
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
                continue
            if header is None:
                header = cells
                continue
            if len(header) != len(cells):
                raise ValueError("Table row width differs from canonical header")
            out.append("- " + "; ".join(f"{h}: {c}" for h, c in zip(header, cells)))
        else:
            header = None
            out.append(line)
    return "\n".join(out).strip() + "\n"


def plain(text: str) -> str:
    text = flatten_tables(text)
    text = LINK.sub(lambda m: f"{m[1]}: {m[2]}", text)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    return text.replace("**", "").replace("`", "")


def bbcode(text: str, platform: str) -> str:
    text = flatten_tables(text)
    text = LINK.sub(lambda m: f"[url={m[2]}]{m[1]}[/url]", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/b]", text)
    text = re.sub(r"`([^`]+)`", r"[b]\1[/b]", text)
    out = []
    listing = None

    def close() -> None:
        nonlocal listing
        if listing:
            out.append("[/olist]" if listing == "ordered" and platform == "steam" else "[/list]")
            listing = None

    for line in text.splitlines():
        item = re.match(r"^(?:([-*])\s+|\d+\.\s+)(.*)", line)
        if item:
            kind = "unordered" if item[1] else "ordered"
            if listing != kind:
                close()
                out.append("[olist]" if kind == "ordered" and platform == "steam" else "[list=1]" if kind == "ordered" else "[list]")
                listing = kind
            out.append("[*]" + item[2])
            continue
        close()
        heading = re.match(r"^#{1,6}\s+(.+)", line)
        if heading:
            out.append(f"[h1]{heading[1]}[/h1]" if platform == "steam" else f"[size=5][b]{heading[1]}[/b][/size]")
        else:
            out.append(line)
    close()
    return "\n".join(out).strip() + "\n"


def visible_words(text: str, is_bbcode: bool = False) -> list[str]:
    if is_bbcode:
        text = unformat_bbcode(text)
    text = re.sub(r"(?m)^(?:[-*]\s+|\d+\.\s+)", "", text)
    return text.split()


def validate(source: str, outputs: dict[str, str]) -> list[dict]:
    checks = []

    def check(name: str, ok: bool) -> None:
        checks.append({"name": name, "passed": bool(ok)})
        if not ok:
            raise ValueError(f"Publication validation failed: {name}")

    check("exact_public_title", source.splitlines()[0] == "# " + TITLE)
    checks.extend(validate_support_and_catalog(source, "canonical", "markdown"))
    for name, output in outputs.items():
        is_bbcode = name.endswith("bbcode.txt")
        platform = "nexus" if "nexus" in name else "steam" if "steam" in name else "paradox"
        canonical = plain(platform_source(source, platform))
        check(name + ": complete_visible_content", visible_words(output, is_bbcode) == visible_words(canonical))
        check(name + ": no_unresolved_template_tokens", not re.search(r"\{\{[^}]+\}\}|<<[^>]+>>", output))
        check(name + ": no_markdown_table", not re.search(r"(?m)^\|", output))
        check(name + ": plain_contact_email", "g4vv4kh@gmail.com" in output and "mailto:" not in output)
        checks.extend(validate_support_and_catalog(output, platform, "bbcode" if is_bbcode else "plain"))
    check("steam_project_profile_under_7999_bytes", len(outputs["description-steam.bbcode.txt"].encode("utf-8")) < 7999)
    paradox = outputs["description-paradox.txt"]
    html_projection = "".join("<p>" + html.escape(p).replace("\n", "<br>") + "</p>" for p in paradox.strip().split("\n\n"))
    check("paradox_project_profile_under_10000_utf16_units", len(paradox.encode("utf-16-le")) // 2 < 10000 and len(html_projection.encode("utf-16-le")) // 2 < 10000)
    return checks


INSTALL_TEMPLATE = """Vassalization Extended 0.2.0 — manual installation
Release candidate: {build_id}
Targets Crusader Kings III 1.20. No additional mod is required.
Vanilla routes to unlock Forced Vassalization retain their own requirements.

The prepared local RC entry

If this release candidate has already been registered in your launcher, use
the public entry named Vassalization Extended. The intended local launcher file
is {local_wrapper}. Setup may reuse an existing entry, so its filename suffix
can refer to an earlier candidate; the build ID and target directory identify
the current candidate. Until local setup is complete, the entry may still point
to the earlier build. Do not add a duplicate entry or also enable the [DEV] copy.
You do not need to extract the manual ZIP over the development installation.
Choose the enabled mods yourself; this package does not change your playset.

Manual ZIP installation on another setup

1. Close the game. Keep a separate copy of any campaign you intend to test.
2. Locate your actual Documents/Paradox Interactive/Crusader Kings III/mod/
   folder. Windows Documents may be redirected, for example through OneDrive.
3. Extract these two sibling entries from the NEXUS-MANUAL ZIP into that folder:

   mod/
     vassalization_extended.mod
     vassalization_extended/
       descriptor.mod
       thumbnail.png
       common/
       gui/
       localization/

   Do not put the wrapper inside the vassalization_extended folder, and do not
   add an extra archive-name folder around the two entries.
4. Preserve an existing installation before replacing files. In particular,
   the author's local DEV wrapper may already be named vassalization_extended.mod.
   Do not overwrite that wrapper with this manual-download wrapper; use the
   separately registered local RC entry described above instead.
5. Open the launcher and add Vassalization Extended to your chosen playset.
   Disable duplicate DEV or older copies of the same mod. Start the game.

Using the mod

With access to Forced Vassalization, open Declare War against an eligible
neighboring independent ruler of lower rank. Expand the Vassalization group,
choose the terms, then read the cost and victory/defeat preview. Low and High
Obligations require a feudal target. Religious Protection has its own vanilla
eligibility conditions. Peaceful vassalization is unchanged.

Compatibility and saves

The mod replaces the Forced Vassalization CB file, the Declare War window and
the vanilla subject-contract group file. Load order cannot merge competing
replacements of these files. No total-conversion compatibility is claimed.

Keep the mod enabled for campaigns using its wars or protected contracts.
Removing it or downgrading during such a campaign is unsupported. Use separate
saves for this release candidate. See TESTING-AND-SCREENSHOTS.ru.txt in the
preparation pack for the planned reload, inheritance and screenshot checks.

This is a prepared release candidate, not a published store download.
Contact: g4vv4kh@gmail.com
"""

RELEASE_INSTALL = """Vassalization Extended 0.2.0 — manual installation
For Crusader Kings III 1.20

Installation

1. Close the game and back up your campaign save.
2. Locate Documents/Paradox Interactive/Crusader Kings III/mod/.
   Use your actual Documents folder; Windows may redirect it through OneDrive.
3. Extract the folder and its sibling .mod file from this archive into mod/:

   mod/
     vassalization_extended.mod
     vassalization_extended/
       descriptor.mod
       thumbnail.png
       common/
       gui/
       localization/

   Do not place the .mod file inside the mod's folder or add an extra enclosing
   archive folder. Preserve an existing installation before replacing it.
4. Open the launcher and add Vassalization Extended to your playset.
   Enable one copy of the mod, then start the game.

Using the mod

With access to Forced Vassalization, open Declare War against an eligible
neighboring independent ruler of lower rank. Expand the Vassalization group,
choose the terms, and read the price and victory/defeat preview. Low and High
Obligations require a feudal target. Religious Protection follows the vanilla
eligibility conditions for religious rights. Peaceful vassalization is unchanged.

Compatibility and saves

No additional mod is required. The mod adds no DLC requirement; vanilla unlock
routes retain their own requirements. English and Russian text is included.

The mod replaces the Forced Vassalization CB file, the Declare War window and
the vanilla subject-contract group file. Load order cannot merge competing
replacements of these files. No total-conversion compatibility is claimed.

Keep the mod enabled for campaigns using its wars or protected contracts.
Removing it or downgrading during such a campaign is unsupported.

Contact: g4vv4kh@gmail.com
"""

TESTING_TEMPLATE = """Vassalization Extended 0.2.0 — проверка {candidate_label} и скриншоты
Сборка: {build_id}
Игра: CK3 1.20.0.3

Это план следующих проверок. Фактическая перезагрузка сохранения, наследование,
новый контраст заголовка и галерея скриншотов {candidate_label} пока не подтверждены.
Предыдущий пользовательский прогон проверял более ранний вид заголовка группы.

1. Выбор сборки

Закрой игру. В своём плейсете включи публичный Vassalization Extended и отключи
[DEV] Vassalization Extended и другие копии этого мода. Планируемый файл записи
лаунчера: {local_wrapper}. Существующая запись может быть перенаправлена
на новый GAME-каталог; прежний суффикс файла не означает старую сборку.
Кандидат определяется идентификатором сборки и её каталогом. До завершения
локальной установки запись может ещё указывать на предыдущий кандидат.
Не добавляй дубликат записи. DEV не заменяется. Выбор плейсета остаётся за тобой.
Локальную {candidate_label} не нужно устанавливать поверх
DEV из ручного ZIP. Сохрани исходный vas_cb_1 отдельно и не перезаписывай его.

2. Загрузка и условия договоров

Загрузи отдельную копию vas_cb_1 с включённой {candidate_label}. Проверь, что у польского
короля сохраняются высокие феодальные обязательства, а у племенного правителя
Пруссии — религиозная защита. Запиши имена текущих вассалов и сюзерена.
Ожидаемые базовые уровни высокого договора: налоги 3 / ополчение 3
(15% / 35% до модификаторов); религиозная защита племенного вассала включена,
его обычные племенные обязательства не превращаются в феодальные.

Сохрани игру отдельным именем vas_{candidate}_before_reload, выйди в главное меню
и действительно загрузи это сохранение заново. Повторно открой оба договора.
После проверки создай vas_{candidate}_after_load. Само наличие двух сохранений без
реального выхода и повторной загрузки не подтверждает перезагрузку.
Если имя уже занято, добавь дату или номер, сохранив предыдущий файл.

3. Наследование

Перед сменой правителя сделай отдельное сохранение vas_{candidate}_before_succession.
Проверь обычное наследование сюзерена, затем наследование защищённого вассала
на отдельной ветке сохранения или при дальнейшей игре. Для каждой проверки
запиши, кто умер, кто наследовал и сохранилась ли вассальная связь.

Если новый правитель остаётся в той же вассальной связи, ожидаются сохранение
высоких обязательств и религиозной защиты соответствующего договора. Сверь
уровни в интерфейсе и возможность требований обращения/отзыва титула. Защита
не запрещает любой отзыв: она убирает освобождение от тирании только по вере.
Другое основание для законного отзыва не означает поломку религиозной защиты.

После события создай vas_{candidate}_after_succession; для второй ветки добавь
_liege или _vassal. Если персонаж стал независимым или вассальная связь
изменилась по обычным правилам наследования, запиши этот исход отдельно.
Он сам по себе не доказывает исчезновение защиты внутри прежнего договора.

Наследование во время активной войны — отдельная проверка: сохранить до
наследования, записать выбранные условия, проверить их после смены участника
и при заключении мира. Мирное наследование договора эту проверку не заменяет.
Для текущего теста не требуется заново запускать весь набор войн.

4. Новый заголовок и скриншоты

Открой Declare War против подходящей цели. Проверь, что заголовок общей
группы читается на фоне, сворачивается и разворачивается, а выбор условий
работает. Для подходящего феодального правителя ожидаются четыре варианта;
для нефеодального — Normal Obligations и Religious Protection. Недоступная
религиозная защита должна иметь понятную причину в подсказке.

Сохрани оригинальные скриншоты без обрезки и изменения содержимого:

01-vassalization-options — раскрытая группа с четырьмя феодальными вариантами.
02-terms-cost-and-outcome — выбранный вариант, цена и полезная подсказка/исход.
03-high-obligations — договор с высокими налогами и ополчением после победы.
04-religious-protection — религиозная защита племенного вассала в договоре.
05-after-succession — тот же договор после наследования, если это понятно
из кадра; до/после можно сохранить отдельной парой для проверки.

Для сравнения цен переключай условия у одной и той же пары правителей:
Low и Religious — 75%, Normal — 100%, High — 150% обычной цены престижа.
Итог зависит от ванильных расчётов, поэтому разные цели не подходят для
прямого сравнения этих множителей. Для галереи достаточно читаемого примера.

Публикационные кадры лучше снять на английском интерфейсе в обычном игровом
разрешении, без консоли и отладочных ID. Подсказки, объясняющие механику,
оставляй. Тестовые доказательства могут быть на русском и с нужными данными.
Подготовка уменьшенных копий и подписей будет отдельным шагом; оригиналы
сохрани. AI-обложка не заменяет настоящие игровые скриншоты.

Что приложить к результату

Укажи сборку {candidate_label}, версию игры, включённые моды, проверенные ветки наследования
и наблюдаемый результат. Приложи vas_{candidate}_after_load и
vas_{candidate}_after_succession (или их варианты), исходные кадры и свежие логи
того же запуска. Если проверялось только наследование одного участника,
так и отметь: это не подтверждает остальные сценарии.
"""

def render_guides(candidate: str, build_id: str, launcher_wrapper: str) -> dict[str, str]:
    if candidate == "release":
        return {"INSTALL.txt": RELEASE_INSTALL}
    fields = {
        "candidate": candidate,
        "candidate_label": candidate.upper(),
        "build_id": build_id,
        "local_wrapper": launcher_wrapper,
    }
    return {
        "INSTALL.txt": INSTALL_TEMPLATE.format_map(fields),
        "TESTING-AND-SCREENSHOTS.ru.txt": TESTING_TEMPLATE.format_map(fields),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--build-id", required=True)
    parser.add_argument("--candidate", choices=("rc1", "rc2", "release"), default="rc1")
    parser.add_argument("--launcher-wrapper", help="Existing or planned local .mod basename; default derives from version and candidate.")
    args = parser.parse_args()
    wrapper = args.launcher_wrapper or ("vassalization_extended.mod" if args.candidate == "release" else f"game_vassalization_extended_0_2_0_{args.candidate}.mod")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.mod", wrapper):
        parser.error("--launcher-wrapper must be a .mod basename")
    source_path = ROOT / "publishing/description.en.md"
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8-sig")
    outputs = {
        "description-steam.bbcode.txt": bbcode(source, "steam"),
        "description-paradox.txt": plain(source),
        "description-nexus.bbcode.txt": bbcode(platform_source(source, "nexus"), "nexus"),
    }
    checks = validate(source, outputs)
    guides = render_guides(args.candidate, args.build_id, wrapper)
    for name, guide in guides.items():
        valid = not re.search(r"\{(?:candidate|candidate_label|local_wrapper|build_id)\}", guide)
        if args.candidate != "release":
            valid = valid and args.build_id in guide and wrapper in guide
        if not valid:
            raise ValueError(f"Guide identity is incomplete: {name}")
        checks.append({"name": name + ": candidate_identity", "passed": True})
    if args.candidate == "release":
        public_text = source + guides["INSTALL.txt"]
        if re.search(r"\[DEV\]|\bRC[12]\b|\blocal development\b|\bdevelopment build\b|\bprototype\b", public_text, re.I):
            raise ValueError("Release player copy contains internal development instructions")
        if (args.output_dir / "TESTING-AND-SCREENSHOTS.ru.txt").exists():
            raise ValueError("Release output contains a candidate test guide; use a separate release output directory")
        checks.append({"name": "release_copy_has_no_development_flow", "passed": True})
    else:
        if not all(f"vas_{args.candidate}_{suffix}" in guides["TESTING-AND-SCREENSHOTS.ru.txt"] for suffix in ("after_load", "after_succession")):
            raise ValueError("Testing guide has incorrect candidate save names")
        checks.append({"name": "test_guide_candidate_save_names", "passed": True})
    extras = {}
    gallery_records = []
    if args.candidate == "release":
        from render_readme import GALLERY, render_readme
        extras["README.md"] = render_readme(source)
        checks.extend(validate_support_and_catalog(extras["README.md"], "github", "markdown"))
        for name, caption in GALLERY:
            rel = "publishing/media/gallery/" + name
            data = (ROOT / rel).read_bytes()
            gallery_records.append({"path": rel, "caption": caption, "sha256": sha256(data), "bytes": len(data)})
        if source.rstrip() not in extras["README.md"]:
            raise ValueError("GitHub README does not preserve the canonical description")
        checks.append({"name": "github_readme_canonical_description_preserved", "passed": True})
        checks.append({"name": "github_gallery_references_exist", "passed": True})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, text in {**outputs, **guides, **extras}.items():
        (args.output_dir / name).write_bytes(text.encode("utf-8"))
    (args.output_dir / "description.en.md").write_bytes(source_bytes)
    source_record = {"path": "publishing/description.en.md", "sha256": sha256(source_bytes), "bytes": len(source_bytes)}
    output_records = [{"path": name, "sha256": sha256(text.encode("utf-8")), "bytes": len(text.encode("utf-8"))} for name, text in {**outputs, **extras}.items()]
    guide_records = [{"path": name, "sha256": sha256(text.encode("utf-8")), "bytes": len(text.encode("utf-8"))} for name, text in guides.items()]
    metadata = {
        "public_title": TITLE,
        "short_description": "Remove the Forced Vassalization county limit and choose low, normal, high or religious peace terms before declaring war.",
        "version": "0.2.0",
        "candidate": args.candidate.upper(),
        "build_id": args.build_id,
        "local_launcher_wrapper": wrapper,
        "supported_version": "1.20.*",
        "compatibility_target": GAME_TARGET,
        "nexus_file_version": "0.2.0",
        "nexus_file_description": f"For CK3 {GAME_TARGET}",
        "description_language": "English",
        "game_localization_languages": ["English", "Russian"],
        "descriptor_tags": ["Gameplay", "Balance", "Warfare"],
        "additional_required_mods": [],
        "additional_dlc_requirement": None,
        "dlc_note": "Vanilla unlock routes retain their own DLC requirements.",
        "contact_email": "g4vv4kh@gmail.com",
        "publication_status": "NOT_PUBLISHED",
        "text_status": "PREPARED_FROM_CANONICAL_SOURCE",
        "platform_ids": {},
        "platform_urls": platform_urls(source),
        "canonical_description": source_record,
        "rendered_outputs": output_records,
        "guides": guide_records,
        "before_external_publication": [
            "Verify required AI promotional-art labels in the actual upload form.",
            "Assign platform links only after real pages exist; add them to the canonical source.",
            "Confirm final platform fields and rendered formatting in the upload forms."
        ],
        "provenance_note": "Promotional cover is AI-generated; authentic gameplay screenshots must be identified separately.",
        "nexus_support_profile": "The approved Ko-fi CTA and URL are preserved, matching the other platforms; no support paragraph is omitted or reworded.",
        "external_publication_performed": False,
    }
    if args.candidate != "release":
        metadata["pending_rc_checks"] = ["Actual save reload", "Succession", "Post-playtest group-header contrast", "Authentic gameplay gallery captures"]
    else:
        metadata["gallery"] = gallery_records
    report = {
        "status": "PASS",
        "scope": "Text rendering only; no engine, visual, upload-form or publication verification.",
        "build_id": args.build_id,
        "candidate": args.candidate.upper(),
        "generator": {"path": "tools/render_publication.py", "sha256": sha256(Path(__file__).read_bytes())},
        "canonical_description": source_record,
        "checks": checks,
        "outputs": output_records,
        "guides": guide_records,
        "canonical_source_unchanged": source_path.read_bytes() == source_bytes,
        "profile_limits_source": "Project publication contract 1.3.1; no live platform form queried by this renderer.",
    }
    for name, data in (("metadata.json", metadata), ("text-render-verification.json", report)):
        (args.output_dir / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks_passed": len(checks), "output_dir": str(args.output_dir), "canonical_sha256": source_record["sha256"]}))


if __name__ == "__main__":
    main()
