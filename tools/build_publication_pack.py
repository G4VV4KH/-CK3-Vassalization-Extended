"""Build/verify an immutable localization update from published version 0.2.0.

All input/output locations are explicit. Never launches CK3, changes a launcher
profile, creates a repository or publishes externally. Existing builds are never
overwritten. A Steam item ID is a descriptor overlay for that platform only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

SLUG = "vassalization_extended"
TITLE = "Vassalization Extended"
VERSION = "0.2.1"
GAME_VERSION = "1.20.0.3"
ROOT = Path(__file__).resolve().parents[1]
BASELINE_FINGERPRINT = "3223999fe8e4f1f0c103f7379cc6f1760272f4338fd35f2da2c34a3f3ac86cc8"
LANGUAGES = ("english", "french", "german", "japanese", "korean", "polish", "russian", "simp_chinese", "spanish")
NEW_LANGUAGES = tuple(language for language in LANGUAGES if language not in ("english", "russian"))
BASE_RUNTIME = {
    "descriptor.mod", "thumbnail.png", "gui/interaction_declare_war.gui",
    "common/casus_belli_types/00_vassalization.txt",
    "common/script_values/ve_vassalization_values.txt",
    "common/scripted_effects/ve_vassalization_effects.txt",
    "common/scripted_triggers/ve_vassalization_triggers.txt",
    "common/subject_contracts/contracts/ve_religious_protection.txt",
    "common/subject_contracts/groups/subject_contract_groups.txt",
    "localization/english/ve_profiles_l_english.yml",
    "localization/russian/ve_profiles_l_russian.yml",
    "localization/replace/vassalization_extended_l_english.yml",
    "localization/replace/vassalization_extended_l_russian.yml",
}
ADDED_RUNTIME = {path for language in NEW_LANGUAGES for path in (
    f"localization/{language}/ve_profiles_l_{language}.yml",
    f"localization/replace/vassalization_extended_l_{language}.yml",
)}
RUNTIME = BASE_RUNTIME | ADDED_RUNTIME
GALLERY = (
    "01-vassalization-options.jpg", "02-low-obligations-victory.jpg",
    "03-low-obligations-defeat.jpg", "04-low-obligations-white-peace.jpg",
)
BASE_SOURCE_EXTRA = {
    ".gitignore", "README.md", "dev.md", "docs/upstream.json",
    "publishing/description.en.md", "publishing/media/provenance.json",
    "publishing/media/rc1-landscape.prompt.txt",
    "publishing/media/cover-square-1024.png", "publishing/media/cover-paradox-1920x1080.png",
    "tools/build_profiles.py", "tools/build_contract_groups.py", "tools/build_localization.py",
    "tools/verify_source.py", "tools/verify_profiles.py", "tools/render_readme.py",
    "tools/render_publication.py", "tools/export_media.ps1", "tools/build_publication_pack.py",
    "publishing/media/gallery/manifest.json",
} | {"publishing/media/gallery/" + name for name in GALLERY}
SOURCE_EXTRA = BASE_SOURCE_EXTRA | {"tools/verify_localization.py"} | {f"tools/localization/{language}.json" for language in LANGUAGES}
TEXTS = {
    "description.en.md", "README.md", "description-steam.bbcode.txt",
    "description-paradox.txt", "description-paradox.html", "description-nexus.bbcode.txt", "INSTALL.txt",
    "metadata.json", "text-render-verification.json", "renderer-profile-checks.json",
}
EVIDENCE = ("SOURCE-EXPORT.json", "source-command-checks.json", "source-static-verification.json", "source-export-checks.json", "source-localization-verification.json")
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def record(data):
    return {"bytes": len(data), "sha256": sha(data)}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def inventory(files):
    return {name: record(data) for name, data in sorted(files.items())}


def fingerprint(files):
    return sha(json.dumps(inventory(files), sort_keys=True, separators=(",", ":")).encode())


def check_localization_update(payload, baseline_inventory, baseline_descriptor):
    """Only a version bump and the fourteen named translation files are allowed."""
    require(set(baseline_inventory) == BASE_RUNTIME, "Baseline runtime inventory differs")
    require(sha(json.dumps(baseline_inventory, sort_keys=True, separators=(",", ":")).encode()) == BASELINE_FINGERPRINT, "Baseline inventory is not published 0.2.0")
    require(record(baseline_descriptor) == baseline_inventory["descriptor.mod"], "Baseline descriptor is not pinned")
    require(set(payload) == RUNTIME, "Localization update runtime inventory differs")
    require(all(record(payload[name]) == baseline_inventory[name] for name in BASE_RUNTIME - {"descriptor.mod"}), "An existing gameplay, GUI, media or EN/RU file changed")
    require(baseline_descriptor.count(b'version="0.2.0"') == 1, "Unexpected baseline version")
    require(payload["descriptor.mod"] == baseline_descriptor.replace(b'version="0.2.0"', b'version="0.2.1"'), "Descriptor delta is not version-only")
    for language in NEW_LANGUAGES:
        for name in (f"localization/{language}/ve_profiles_l_{language}.yml", f"localization/replace/vassalization_extended_l_{language}.yml"):
            require(payload[name].startswith(b"\xef\xbb\xbf" + f"l_{language}:\n".encode()), f"Wrong localization BOM/header: {name}")


def tree(root):
    require(root.is_dir(), f"Missing directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink() and not (getattr(path.lstat(), "st_file_attributes", 0) & 0x400), f"Reparse point: {path}")
        if path.is_file():
            name = path.relative_to(root).as_posix()
            require(name.casefold() not in {key.casefold() for key in result}, f"Case collision: {name}")
            result[name] = path.read_bytes()
    return result


def put(root, files):
    for name, data in files.items():
        require(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts and "\\" not in name and ":" not in name, f"Unsafe output: {name}")
        target = root / name
        require(not target.exists(), f"Refusing overwrite: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def png_size(data):
    require(data[:8] == b"\x89PNG\r\n\x1a\n", "Invalid PNG")
    return struct.unpack(">II", data[16:24])


def jpeg_size(data):
    require(data[:2] == b"\xff\xd8", "Invalid JPEG")
    pos = 2
    while pos < len(data):
        require(data[pos] == 255, "Invalid JPEG marker")
        while data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            continue
        size = int.from_bytes(data[pos:pos + 2], "big")
        require(size >= 2, "Invalid JPEG segment")
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[pos + 3:pos + 7])
            return width, height
        pos += size
    raise ValueError("JPEG dimensions not found")


def steam_descriptor(public, steam_id):
    require(b"remote_file_id" not in public, "Baseline has platform identity")
    if steam_id is None:
        return public
    require(re.fullmatch(r"[1-9][0-9]*", steam_id) is not None, "Invalid Steam item ID")
    return public + f'remote_file_id="{steam_id}"\n'.encode()


def zip_write(path, files):
    require(not path.exists(), f"Refusing overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            require(not name.startswith("/") and ".." not in name.split("/") and ":" not in name and "\\" not in name, f"Unsafe ZIP member: {name}")
            info = zipfile.ZipInfo(name, ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def zip_check(path, expected):
    with zipfile.ZipFile(path) as archive:
        require(archive.testzip() is None, f"CRC failure: {path}")
        require(len(archive.namelist()) == len(set(archive.namelist())) and set(archive.namelist()) == set(expected), f"Unexpected ZIP members: {path}")
        require(all(record(archive.read(name)) == rec for name, rec in expected.items()), f"ZIP payload mismatch: {path}")


def check_source(source, version=VERSION):
    allowed = (BASE_RUNTIME | BASE_SOURCE_EXTRA) if version == "0.2.0" else (RUNTIME | SOURCE_EXTRA)
    require(set(source) == allowed, "Source projection differs from the explicit allowlist")
    forbidden = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z]:[/\\]|(?i:Users[/\\]Pavel)|OPENAI_API_KEY\s*=")
    for name, data in source.items():
        if Path(name).suffix in (".py", ".ps1", ".md", ".json", ".txt", ".mod", ".yml", ".gui"):
            require(not forbidden.search(data), f"Machine path or credential in source: {name}")
    readme = source["README.md"].decode("utf-8-sig")
    for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", readme):
        link = link.strip("<>").split("#", 1)[0]
        if not link or re.match(r"[a-z]+:", link, re.I):
            continue
        require(link in source, f"Broken README link: {link}")
    require(all("publishing/media/gallery/" + name in readme for name in GALLERY), "README gallery is incomplete")
    require(b"remote_file_id" not in source["descriptor.mod"], "Platform identity leaked into portable source")


def check_gallery(gallery):
    require(set(gallery) == set(GALLERY) | {"manifest.json"}, "Unexpected gallery inventory")
    manifest = json.loads(gallery["manifest.json"])
    require([entry["file"] for entry in manifest["images"]] == list(GALLERY), "Wrong gallery order")
    for item in manifest["images"]:
        data = gallery[item["file"]]
        require(record(data) == {"bytes": item["bytes"], "sha256": item["sha256"]}, "Gallery manifest mismatch")
        require(jpeg_size(data) == (1920, 1080) and len(data) < 2_000_000, "Gallery image dimensions/size invalid")
    require(sum(len(gallery[name]) for name in GALLERY) < 8_000_000, "Gallery batch too large")
    require(manifest["ai_generated"] is False, "Authentic gallery provenance missing")


def verify(bundle):
    manifest = json.loads((bundle / "07-VERIFICATION/manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    require(version in ("0.2.0", VERSION), "Unsupported publication version")
    expected_runtime = BASE_RUNTIME if version == "0.2.0" else RUNTIME
    payload = tree(Path(manifest["game_directory"]) / SLUG)
    require(set(payload) == expected_runtime, "GAME runtime inventory changed")
    require(inventory(payload) == manifest["mods"][SLUG]["game"], "GAME manifest mismatch")
    require(fingerprint(payload) == manifest["runtime_fingerprint"], "Runtime fingerprint differs")
    lock_raw = (bundle / "07-VERIFICATION/release-inputs.json").read_bytes()
    lock = json.loads(lock_raw)
    if version == "0.2.0":
        require(fingerprint(payload) == BASELINE_FINGERPRINT, "Legacy runtime differs from reviewed baseline")
    else:
        check_localization_update(payload, lock["baseline_runtime_inputs"], lock["baseline_descriptor_utf8"].encode("utf-8"))
    public = payload["descriptor.mod"]
    require(f'name="{TITLE}"'.encode() in public and f'version="{version}"'.encode() in public, "Wrong descriptor identity")
    require(b'picture="thumbnail.png"' in public and not re.search(rb"(?m)^\s*(?:remote_file_id|path|replace_path)\s*=", public), "Nonportable GAME descriptor")
    expected_steam = {**payload, "descriptor.mod": steam_descriptor(public, manifest["steam_overlay"]["remote_file_id"])}
    require(tree(bundle / "01-STEAM/runtime" / SLUG) == expected_steam, "Steam overlay differs from approved ID-only transform")
    require(inventory(expected_steam) == manifest["mods"][SLUG]["steam"], "Steam target manifest mismatch")
    wrapper = public + f'path="mod/{SLUG}"\n'.encode()
    require((bundle / "01-STEAM/runtime" / f"{SLUG}.mod").read_bytes() == wrapper, "Portable wrapper changed")
    for item in manifest["archives"]:
        archive = bundle / item["path"]
        require(record(archive.read_bytes()) == item["file"], "Archive container hash mismatch")
        zip_check(archive, item["members"])
    require(len(manifest["archives"]) == 2, "Wrong archive count")
    require(manifest["archives"][0]["members"] == inventory(payload), "Paradox archive is not the clean runtime")
    nexus = {**{f"{SLUG}/{name}": data for name, data in payload.items()}, f"{SLUG}.mod": wrapper, "INSTALL.txt": (bundle / "02-TEXT/INSTALL.txt").read_bytes()}
    require(manifest["archives"][1]["members"] == inventory(nexus), "Nexus manual layout is wrong")
    source = tree(bundle / "06-GITHUB/source")
    require(inventory(source) == manifest["source_projection"], "Source projection differs")
    check_source(source, version)
    require(all(source[name] == data for name, data in payload.items()), "Portable source/runtime mismatch")
    check_gallery(tree(bundle / "05-IMAGES/GALLERY"))
    require(png_size(payload["thumbnail.png"]) == (512, 512) and len(payload["thumbnail.png"]) < 1_000_000, "Steam thumbnail invalid")
    cover = (bundle / "05-IMAGES/cover-paradox-1920x1080.jpg").read_bytes()
    require(jpeg_size(cover) == (1920, 1080) and len(cover) < 2_000_000, "Paradox JPEG invalid")
    require(sha(lock_raw) == manifest["input_lock_sha256"], "Input lock mismatch")
    require(sha((bundle / "07-VERIFICATION/build_publication_pack.py").read_bytes()) == manifest["builder_sha256"], "Builder snapshot mismatch")
    require(all(record((bundle / name).read_bytes()) == rec for name, rec in manifest["kit_files"].items()), "Kit member changed")
    expected_names = set(manifest["kit_files"]) | {"07-VERIFICATION/manifest.json", "07-VERIFICATION/build-results.json"}
    actual_names = set(tree(bundle))
    require(actual_names in (expected_names, expected_names - {"07-VERIFICATION/build-results.json"}), "Untracked or missing kit file")
    fields = json.loads((bundle / "02-TEXT/release-fields.json").read_bytes())
    require(fields["nexus_file_description"] == f"For CK3 {GAME_VERSION}", "Wrong Nexus file-description field")
    require(fields["candidate"] == "RELEASE", "RC test copy leaked into publication pack")
    return {"status": "PUBLICATION_PACK_VERIFIED", "build_id": manifest["build_id"], "version": version, "runtime_files": len(payload), "runtime_fingerprint": fingerprint(payload), "runtime_matches_rc2": version == "0.2.0", "gameplay_matches_published_0_2_0": True, "localization_only_update": version == VERSION, "new_localization_files": len(ADDED_RUNTIME) if version == VERSION else 0, "steam_remote_file_id": manifest["steam_overlay"]["remote_file_id"], "source_files": len(source), "archives": 2, "gallery_images": 4, "engine_test_performed_by_builder": False, "external_publication_performed": False}


def start_guide(args, fields, game):
    paradox = f"03-PARADOX/vassalization-extended-{VERSION}-PARADOX.zip"
    nexus = f"04-NEXUS/vassalization-extended-{VERSION}-NEXUS-MANUAL.zip"
    gallery = "\n".join(f"{index}. 05-IMAGES/GALLERY/{name}" for index, name in enumerate(GALLERY, 1))
    text = f"""{TITLE} {VERSION} — publication pack
Build: {args.build_id}
Status: PREPARED; this pack does not record an external publication.
Target CK3: {GAME_VERSION}. Public title: {TITLE}
Short description: {fields['short_description']}
Tags: {', '.join(fields['descriptor_tags'])}
Required mods: none. {fields['dlc_note']}
Languages: {', '.join(fields['game_localization_languages'])}. Contact: {fields['contact_email']}

STEAM
Content folder: 01-STEAM/runtime/{SLUG}/
Description: 02-TEXT/description-steam.bbcode.txt
Primary preview: 05-IMAGES/thumbnail.png (512x512 PNG, below 1MB).
Descriptor item ID: {args.steam_id or 'Omitted; the publishing API selects the actual item ID separately. A descriptor overlay is optional.'}
If present, remote_file_id appears only in the Steam content descriptor.

PARADOX
Existing item: {fields['platform_urls']['paradox']}
Archive: {paradox} (descriptor.mod and game folders at ZIP root).
Description: 02-TEXT/description-paradox.html (linked rich text, including the large support heading).
Plain-text fallback: 02-TEXT/description-paradox.txt; it does not preserve heading size or clickable links.
Upload thumbnail: 05-IMAGES/cover-paradox-1920x1080.jpg (full 16:9 composition, below 2MB).
Retained PNG source: 05-IMAGES/cover-paradox-1920x1080.png.
The observed upload form requests JPG below 2MB and displays 1280x720px guidance.
The live form accepted this 1920x1080 JPEG and displayed it with the four gallery
previews on 2026-10-05. This confirms form acceptance, not completed publication.

NEXUS
Existing item: {fields['platform_urls']['nexus']}
Archive: {nexus} (mod directory, sibling .mod wrapper and INSTALL.txt).
Description: 02-TEXT/description-nexus.bbcode.txt
File version: {VERSION}
File Description: For CK3 {GAME_VERSION}
Square cover: 05-IMAGES/cover-square-1024.png

GITHUB
Reviewed source: 06-GITHUB/source/
Source includes README, developer guidance and gallery; no personal campaigns/logs.
Intended destination: {fields.get('platform_urls', {}).get('github', 'Not assigned')}
This directory is a source projection, not a Git publication receipt.

GALLERY ORDER
{gallery}
Captions and hashes: 05-IMAGES/GALLERY/manifest.json.
These authentic screenshots show the choice of terms and outcome previews.
They are distinct from the AI-generated promotional cover (05-IMAGES/provenance.json).

INSTALLATION AND COMPATIBILITY
Use 02-TEXT/INSTALL.txt for manual installation. Do not enable duplicate copies.
The mod replaces the Forced Vassalization CB, Declare War GUI and subject-contract groups.
Other mods replacing those files require a compatibility patch. Keep the mod enabled
in campaigns using its custom wars/contracts; removal/downgrade is unsupported.

VERIFICATION AND STATUS
Frozen clean GAME copy: {(game / SLUG).as_posix()}
Localization-only update from published 0.2.0: fourteen new localization YAML files
and the descriptor version 0.2.1. Gameplay, GUI, thumbnail and existing English/Russian
localization bytes are unchanged. New translations have not been visually certified
by this packaging process. Historical gameplay evidence does not prove UI fit in
every language; no new engine test is performed by the builder.
Input lock, per-target hashes and ZIP CRC/payload checks: 07-VERIFICATION/.
PUBLICATION-STATUS.json is the immutable prepared snapshot, not a live status page.
Mutable publication journal outside this kit: {args.journal.resolve().as_posix()}
Store acceptance, public pages and delivered bytes require separate publication records.
"""
    page = "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\"><title>" + html.escape(TITLE) + " — publication pack</title><style>body{font:17px/1.6 system-ui;background:#171c24;color:#eee6d6;max-width:1100px;margin:36px auto;padding:0 24px}h1{color:#e4bd6d}a{color:#b2d7fa}pre{white-space:pre-wrap;font:inherit}img{max-width:100%;border-radius:8px}button{font:inherit;padding:8px 16px;cursor:pointer}</style><h1>" + html.escape(TITLE + " " + VERSION) + "</h1><p>Prepared for publication; upload and delivered-byte verification are separate steps.</p><button onclick=\"navigator.clipboard.writeText('Vassalization Extended')\">Copy title</button><p><a href=\"02-TEXT/release-fields.json\">Publication fields</a> · <a href=\"PUBLICATION-STATUS.json\">Prepared status</a> · <a href=\"02-TEXT/INSTALL.txt\">Installation</a></p><img src=\"05-IMAGES/cover-paradox-1920x1080.jpg\" alt=\"AI-generated promotional homage scene\"><pre>" + html.escape(text) + "</pre></html>"
    return {"00-START-HERE.txt": text.encode("utf-8"), "00-START-HERE.html": page.encode("utf-8")}


def append_journal(path, event):
    if path.exists():
        journal = json.loads(path.read_text(encoding="utf-8-sig"))
        require(journal.get("mod") == SLUG and isinstance(journal.get("events"), list), "Unexpected mutable journal schema")
    else:
        journal = {"schema": 1, "mod": SLUG, "note": "Mutable publication progress; independent from immutable prepared kits.", "events": []}
    journal["events"].append(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(journal))


def build(args):
    stage, release = args.inputs_stage.resolve(), args.release_root.resolve()
    game, bundle = release / "game" / args.build_id, release / "deploy" / args.bundle_name
    require(not game.exists() and not bundle.exists(), "Refusing to overwrite a frozen build or publication kit")
    require(args.journal.resolve() != bundle and bundle not in args.journal.resolve().parents and game not in args.journal.resolve().parents, "Mutable journal must be outside frozen artifacts")
    if args.journal.exists():
        journal = json.loads(args.journal.read_text(encoding="utf-8-sig"))
        require(journal.get("mod") == SLUG and isinstance(journal.get("events"), list), "Unexpected mutable journal schema")
    baseline_manifest_path = args.baseline_bundle.resolve() / "07-VERIFICATION/manifest.json"
    baseline_manifest_raw = baseline_manifest_path.read_bytes()
    baseline_manifest = json.loads(baseline_manifest_raw)
    require(baseline_manifest["version"] == "0.2.0" and baseline_manifest["candidate"] == "RELEASE", "Use the frozen published 0.2.0 baseline")
    baseline = tree(args.baseline_runtime.resolve())
    require(set(baseline) == BASE_RUNTIME and fingerprint(baseline) == BASELINE_FINGERPRINT, "Baseline is not the exact published 0.2.0 runtime")
    require(inventory(baseline) == baseline_manifest["mods"][SLUG]["game"] and baseline_manifest["runtime_fingerprint"] == BASELINE_FINGERPRINT, "Baseline manifest mismatch")
    baseline_bundle_fingerprint = fingerprint(tree(args.baseline_bundle.resolve()))
    for output in (game, bundle):
        for immutable in (args.baseline_bundle.resolve(), args.baseline_runtime.resolve()):
            require(output != immutable and immutable not in output.parents and output not in immutable.parents, "Output overlaps an immutable baseline")
    source = tree(stage / "source-export")
    check_source(source)
    payload = {name: source[name] for name in RUNTIME}
    check_localization_update(payload, inventory(baseline), baseline["descriptor.mod"])
    public = payload["descriptor.mod"]
    require(args.steam_id == "3813943691", "This update must retain the assigned Steam item")
    steam = {**payload, "descriptor.mod": steam_descriptor(public, args.steam_id)}
    wrapper = public + f'path="mod/{SLUG}"\n'.encode()
    require(source["tools/build_publication_pack.py"] == Path(__file__).read_bytes(), "Source projection contains an older pack builder")
    texts = tree(stage / "texts")
    require(set(texts) == TEXTS, "Unexpected release-text inventory")
    fields = json.loads(texts["metadata.json"])
    require(fields["candidate"] == "RELEASE" and fields["build_id"] == args.build_id, "Texts were rendered for a different build")
    require(fields["public_title"] == TITLE and fields["version"] == VERSION and fields["compatibility_target"] == GAME_VERSION, "Wrong text metadata identity")
    require(texts["description.en.md"] == source["publishing/description.en.md"] and texts["README.md"] == source["README.md"], "Refresh the source projection and texts together")
    require(record(texts["description.en.md"]) == {key: fields["canonical_description"][key] for key in ("bytes", "sha256")}, "Canonical metadata hash mismatch")
    for item in fields["rendered_outputs"] + fields["guides"]:
        require(record(texts[item["path"]]) == {key: item[key] for key in ("bytes", "sha256")}, "Generated text hash mismatch")
    require(fields["nexus_file_description"] == f"For CK3 {GAME_VERSION}", "Wrong Nexus file description")
    require(b"TESTING-AND-SCREENSHOTS" not in texts["INSTALL.txt"] and b"vas_rc" not in texts["INSTALL.txt"], "RC test instructions leaked into installation guide")
    fields = dict(fields)
    assigned_urls = {"steam": "https://steamcommunity.com/sharedfiles/filedetails/?id=3813943691", "paradox": "https://mods.paradoxplaza.com/mods/162059/Any", "nexus": "https://www.nexusmods.com/crusaderkings3/mods/407", "github": "https://github.com/G4VV4KH/-CK3-Vassalization-Extended"}
    require(fields["platform_urls"] == assigned_urls, "Assigned platform links changed")
    fields["platform_ids"] = {"steam": "3813943691", "paradox": "162059", "nexus": "407"}
    fields["steam_item_id_for_prepared_payload"] = args.steam_id
    texts["release-fields.json"] = json_bytes(fields)
    gallery = {name: source["publishing/media/gallery/" + name] for name in (*GALLERY, "manifest.json")}
    check_gallery(gallery)
    baseline_images = args.baseline_bundle.resolve() / "05-IMAGES"
    assets = {name: (baseline_images / name).read_bytes() for name in ("thumbnail.png", "cover-square-1024.png", "cover-paradox-1920x1080.png", "landscape.prompt.txt")}
    require(assets["thumbnail.png"] == payload["thumbnail.png"], "Thumbnail differs from published 0.2.0")
    for name in ("cover-square-1024.png", "cover-paradox-1920x1080.png"):
        require(assets[name] == source["publishing/media/" + name], "Cover changed since published 0.2.0")
    upload_jpeg = args.paradox_jpeg.resolve().read_bytes()
    require(jpeg_size(upload_jpeg) == (1920, 1080) and len(upload_jpeg) < 2_000_000, "Invalid Paradox JPEG")
    require(upload_jpeg == (baseline_images / "cover-paradox-1920x1080.jpg").read_bytes(), "Paradox cover changed during localization-only update")
    assets["cover-paradox-1920x1080.jpg"] = upload_jpeg
    provenance = json.loads((baseline_images / "provenance.json").read_bytes())
    provenance["publication_revision"] = {"reason": "Paradox live form requests JPG below 2MB; retain the approved PNG and full 16:9 composition.", "operation": "JPEG compression only, quality 95, no crop or resize", "png_source": {"path": "cover-paradox-1920x1080.png", **record(assets["cover-paradox-1920x1080.png"])}, "upload_jpeg": {"path": "cover-paradox-1920x1080.jpg", "width": 1920, "height": 1080, **record(upload_jpeg)}, "live_form_guidance": "1280x720px JPG, 2MB maximum", "larger_resolution_acceptance": "Parent agent observed the live form accepting this 1920x1080 JPEG and rendering five cover/gallery previews on 2026-10-05; form acceptance is distinct from completed publication"}
    provenance["gallery"] = {"path": "GALLERY/manifest.json", "ai_generated": False, "scope": "User-provided UI and outcome previews"}
    evidence = {name: (stage / name).read_bytes() for name in EVIDENCE}
    export_record = json.loads(evidence["SOURCE-EXPORT.json"])
    require({item["path"]: {key: item[key] for key in ("bytes", "sha256")} for item in export_record["files"]} == inventory(source), "Source evidence does not describe the current projection")
    export_checks = json.loads(evidence["source-export-checks.json"])
    require(export_checks["status"] == "PASS" and all(item["passed"] for item in export_checks["checks"]), "Source export checks have not passed")
    require(export_checks["source_fingerprint"] == fingerprint(source), "Source export checks are stale")
    static_checks = json.loads(evidence["source-static-verification.json"])
    require(static_checks["status"] == "STATIC_CHECKS_PASSED" and not static_checks["failures"], "Source static checks have not passed")
    commands = json.loads(evidence["source-command-checks.json"])
    require(all(item["exit_code"] == 0 for item in commands["results"]), "A source verification command failed")
    localization_checks = json.loads(evidence["source-localization-verification.json"])
    require(localization_checks["status"] == "LOCALIZATION_CHECKS_PASSED" and localization_checks["file_count"] == 18 and len(localization_checks["languages"]) == 9, "Independent localization checks have not passed")
    evidence["build_publication_pack.py"] = Path(__file__).read_bytes()
    lock = {"schema": 2, "kind": "localization-update-from-published-0.2.0", "build_id": args.build_id, "version": VERSION, "game_target": GAME_VERSION, "baseline_manifest": {"path": baseline_manifest_path.as_posix(), **record(baseline_manifest_raw)}, "baseline_runtime_fingerprint": BASELINE_FINGERPRINT, "baseline_runtime_inputs": inventory(baseline), "baseline_descriptor_utf8": baseline["descriptor.mod"].decode("utf-8"), "baseline_bundle_fingerprint": baseline_bundle_fingerprint, "runtime_inputs": inventory(payload), "steam_target": inventory(steam), "steam_item_id": args.steam_id, "text_inputs": inventory(texts), "source_projection_inputs": inventory(source), "media_inputs": inventory(assets), "gallery_inputs": inventory(gallery), "evidence_inputs": inventory(evidence), "builder": record(Path(__file__).read_bytes())}
    lock_raw = json_bytes(lock)
    transforms = {"schema": 2, "build_id": args.build_id, "gameplay_matches_published_0_2_0": True, "runtime_files_unchanged": 12, "runtime_files_added": sorted(ADDED_RUNTIME), "descriptor_version_only": {"before": record(baseline["descriptor.mod"]), "after": record(public), "from": "0.2.0", "to": VERSION}, "steam_only": [{"path": "descriptor.mod", "operation": "Append remote_file_id only to the Steam runtime", "remote_file_id": args.steam_id, "before": record(public), "after": record(steam["descriptor.mod"])}], "publication_assets": "Existing approved covers, thumbnail and authentic gallery retained. Public copy and developer guidance updated for nine languages.", "game_launched": False, "launcher_changed": False, "external_publication_performed": False}
    put(game / SLUG, payload)
    put(bundle / "01-STEAM/runtime" / SLUG, steam)
    put(bundle / "01-STEAM/runtime", {f"{SLUG}.mod": wrapper})
    put(bundle / "02-TEXT", texts)
    put(bundle / "05-IMAGES", {**assets, "provenance.json": json_bytes(provenance)})
    put(bundle / "05-IMAGES/GALLERY", gallery)
    put(bundle / "06-GITHUB/source", source)
    put(bundle / "07-VERIFICATION", {**evidence, "release-inputs.json": lock_raw, "transform-report.json": json_bytes(transforms)})
    archives = []
    for name, content in (
        (f"03-PARADOX/vassalization-extended-{VERSION}-PARADOX.zip", payload),
        (f"04-NEXUS/vassalization-extended-{VERSION}-NEXUS-MANUAL.zip", {**{f"{SLUG}/{name}": data for name, data in payload.items()}, f"{SLUG}.mod": wrapper, "INSTALL.txt": texts["INSTALL.txt"]}),
    ):
        zip_write(bundle / name, content)
        archives.append({"path": name, "file": record((bundle / name).read_bytes()), "members": inventory(content)})
    platforms = {}
    for platform in ("steam", "paradox", "nexus", "github"):
        url = fields.get("platform_urls", {}).get(platform)
        remote_id = fields.get("platform_ids", {}).get(platform)
        if platform == "steam" and args.steam_id:
            remote_id = args.steam_id
        if platform == "nexus" and not remote_id and url:
            match = re.fullmatch(r"https://www\.nexusmods\.com/crusaderkings3/mods/([1-9][0-9]*)/?", url)
            remote_id = match.group(1) if match else None
        platforms[platform] = {"status": "PREPARED", "remote_id": remote_id, "assigned_url": url, "publication_verified_by_builder": False}
    status = {"schema": 2, "mod": SLUG, "title": TITLE, "version": VERSION, "build_id": args.build_id, "candidate": "RELEASE", "status": "PREPARED_NOT_PUBLISHED", "game_target": GAME_VERSION, "runtime_baseline": "Published 0.2.0; descriptor version-only plus fourteen new localization files", "screenshots": "FOUR_AUTHENTIC_0_2_0_UI_PREVIEWS_RETAINED", "independent_limits": "New translations are statically checked, not certified by native UI review in every language. Historical screenshots do not establish reload or succession.", "platforms": platforms, "external_publication_performed_by_builder": False, "mutable_publication_journal": args.journal.resolve().as_posix()}
    put(bundle, {"PUBLICATION-STATUS.json": json_bytes(status), **start_guide(args, fields, game)})
    manifest = {"schema": 2, "candidate": "RELEASE", "build_id": args.build_id, "version": VERSION, "input_lock_sha256": sha(lock_raw), "builder_sha256": sha(Path(__file__).read_bytes()), "game_directory": game.as_posix(), "mods": {SLUG: {"source": inventory(payload), "game": inventory(payload), "steam": inventory(steam)}}, "runtime_fingerprint": fingerprint(payload), "baseline_runtime_fingerprint": BASELINE_FINGERPRINT, "steam_overlay": {"remote_file_id": args.steam_id, "scope": "01-STEAM/runtime/vassalization_extended/descriptor.mod only"}, "archives": archives, "source_projection": inventory(source), "kit_files": inventory(tree(bundle))}
    put(game, {"manifest.json": json_bytes(manifest), "transform-report.json": json_bytes(transforms)})
    put(bundle / "07-VERIFICATION", {"manifest.json": json_bytes(manifest)})
    result = verify(bundle)
    require(fingerprint(tree(args.baseline_bundle.resolve())) == baseline_bundle_fingerprint and tree(args.baseline_runtime.resolve()) == baseline, "An immutable baseline changed while building")
    put(bundle / "07-VERIFICATION", {"build-results.json": json_bytes(result)})
    append_journal(args.journal.resolve(), {"recorded_at": datetime.now(timezone.utc).isoformat(), "kind": "LOCALIZATION_PACK_PREPARED", "build_id": args.build_id, "bundle": bundle.as_posix(), "manifest": record(json_bytes(manifest)), "runtime_fingerprint": fingerprint(payload), "baseline_runtime_fingerprint": BASELINE_FINGERPRINT, "immutable_baseline_unchanged": True, "steam_item_id": args.steam_id, "external_publication_performed": False})
    return {**result, "bundle": bundle.as_posix(), "game_runtime": (game / SLUG).as_posix()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-bundle", type=Path)
    parser.add_argument("--baseline-runtime", type=Path)
    parser.add_argument("--inputs-stage", type=Path)
    parser.add_argument("--release-root", type=Path)
    parser.add_argument("--paradox-jpeg", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--build-id", default="2026-10-05-vassalization-extended-0.2.1-release")
    parser.add_argument("--bundle-name", default="vassalization-extended-0.2.1")
    parser.add_argument("--steam-id", default="3813943691", help="Assigned Steam item ID; only its platform descriptor receives this field")
    parser.add_argument("--verify-only", type=Path, metavar="BUNDLE")
    args = parser.parse_args()
    if args.verify_only:
        result = verify(args.verify_only.resolve())
    else:
        require(all((args.baseline_bundle, args.baseline_runtime, args.inputs_stage, args.release_root, args.paradox_jpeg, args.journal)), "Build requires explicit baseline, inputs, output root, Paradox JPEG and journal paths")
        require(re.fullmatch(r"[a-z0-9][a-z0-9.-]*", args.build_id) and re.fullmatch(r"[a-z0-9][a-z0-9.-]*", args.bundle_name), "Unsafe build identifier")
        result = build(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
