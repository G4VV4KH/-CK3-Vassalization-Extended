# Vassalization Extended development

This is the portable source projection for **Vassalization Extended 0.2.1**,
targeting CK3 **1.20.0.3**. This update adds French, German, Japanese, Korean,
Polish, Simplified Chinese and Spanish to the existing English and Russian.
Gameplay scripts, GUI, thumbnail and existing English/Russian localization are
byte-identical to published 0.2.0. The runtime changes are fourteen additional
localization YAML files and the descriptor version. Preparing this source is
distinct from verifying a public repository or store download.

## Source layout

- `common/`, `gui/` and `localization/` contain the game payload.
- `descriptor.mod` uses the public title. The release assembler supplies the
  512×512 `thumbnail.png` named by the descriptor.
- `publishing/description.en.md` is the only editable player description.
  `README.md` is generated from it; platform descriptions are rendered separately.
- `docs/upstream.json` pins the vanilla CB. Its `change` field describes the
  initial county-cap prototype, not the complete scope of version 0.2.0.
- `tools/build_profiles.py`, `build_contract_groups.py` and
  `build_localization.py` generate the reviewed CB, group and localization files.
- `tools/localization/` contains the nine editable JSON translation sources;
  `tools/verify_localization.py` independently checks all eighteen runtime language
  files, substitution tokens, numeric mechanics and missing translations.
- `tools/verify_profiles.py` performs the current independent static checks.
  `verify_source.py` provides its shared parser and forwards command-line calls
  to the current verifier; its retained historical check function is not the
  verifier for this release.

The source projection excludes personal campaigns, logs, archived audit outputs,
raw character-reference screenshots and unused artwork drafts. No license or
additional permission grant has been introduced by the export process.

## Implementation

The county-count gate is removed while the other vanilla eligibility rules are
retained. Four CB profiles record their terms on the war: low, normal, high and
religious protection. The original `vassalization_cb` remains the normal profile.
Low/high terms apply to feudal and Japanese feudal contract groups; other vanilla
governments retain their normal contributions under the normal/protection choices.

Victory resolves the liege change before assigning terms. Feudal levels are
1/1, 2/2, 3/3 and 2/1 respectively, followed by the ordinary contract-negotiation
block. The independent `ve_religious_protection` obligation is appended to all
14 vanilla non-tributary groups and grants the vanilla `religiously_protected`
flag. Existing obligation indices and tributary groups are preserved.

Native setters honor both obligation visibility and change-permission gates.
The victory helper opens both using a transient subject flag, sets level 1 and
immediately removes the flag. The issued right remains visible and cannot be
negotiated away; changing faith does not erase it.

The vanilla religious-rights eligibility, including the Jizya exception, is
evaluated when war is declared. Choosing another profile while protection is
available records a refusal marker. Attacker defeat then costs one devotion
level; faith changes do not recalculate the marker. The current primary leaders
inherit the terms with the war. Existing wars without a marker retain their old
resolution. Some native war memories/messages use generic text for new CB IDs.

## Reproduce static checks

Use Python **3.10 or newer** and an installed copy of the pinned CK3 version.
Python tools use only the standard library. Run from this directory and replace
`<CK3 installation>` with the location of your own game:

```text
python -B tools/build_profiles.py --game-root "<CK3 installation>/game" --check
python -B tools/build_contract_groups.py --game-root "<CK3 installation>/game" --check
python -B tools/build_localization.py --check
python -B tools/verify_localization.py --game-root "<CK3 installation>/game"
python -B tools/verify_profiles.py --game-root "<CK3 installation>/game"
```

Every tool that reads vanilla data requires an explicit `--game-root` in this
export. No default installation path is embedded. The three generator checks
compare existing output without rewriting it. Omit `--check` only when
intentionally regenerating after reviewing a source change. The verifier prints
JSON to stdout; an optional `--report <file>` writes a report into an existing
directory. Static success does not certify engine behavior, AI balance, save
compatibility or visual layout.

Edit generators and helpers instead of hand-editing generated CB/group/profile
localization files. The GUI adapter is delimited by `VE_GROUP_TYPES` and
`VE_GROUP_LIST` markers. The generators/checker pin vanilla CB, group and GUI
inputs; a changed upstream hash requires review and rebasing before updating the
pin. Same-file modifications by other mods require a combined compatibility
patch. Custom contract groups need an adapter.

## Publication text and media

After editing the canonical player description:

```text
python -B tools/render_readme.py
python -B tools/render_publication.py --output-dir "<new staging directory>" --build-id "2026-10-05-vassalization-extended-0.2.1-release" --candidate release
```

The publication renderer works only on this mod, preserves the canonical
content and creates Steam/Nexus BBCode, Paradox plain text and linked HTML, metadata and a rendering
report. It does not publish anything. Its size checks implement the maintained
project profile and do not replace reviewing the actual platform form.
When reusing an existing local launcher entry, pass `--launcher-wrapper` with
that wrapper's filename. Rendering guides does not change launcher settings.

For an existing release's metadata-only update, add
`--metadata-revision "<reviewed metadata revision JSON>"` to the release command.
Resolve that current input through the release registry. It supplies the existing
platform URLs/IDs, Nexus file ID, mod version, CK3 target and canonical hash;
missing or mismatched identity is rejected before writing. Generated metadata
uses `PREPARED_EXTERNAL_VERIFICATION_PENDING`; it does not certify a saved page
or delivered archive. Preserve the existing game archives. Run
`python -B tools/test_render_publication_metadata.py` for the identity gates,
deterministic generation and source-write boundary checks. Without an explicit
existing-release input, the renderer retains the new-release `NOT_PUBLISHED`
state. Candidate mode defaults to `rc1`, so specify `--candidate release` for
public copy.

`tools/export_media.ps1` is an optional **Windows PowerShell/System.Drawing**
utility. Supply `-SquareSource`, `-WideSource` and a new `-OutputDirectory`. It
fits the entire supplied artwork into the 1024×1024 cover, 512×512 thumbnail and
1920×1080 cover without cropping, and refuses to overwrite an existing export
directory. The supplied promotional artwork is AI-generated; it is distinct
from authentic gameplay screenshots. Portable provenance and the landscape
generation brief are in `publishing/media/`.

## Localization update 0.2.1

All nine languages use the same localization keys and retain the same character
substitutions, cross-references, numeric rates and perk lookup. The generator
preserves English/Russian runtime bytes and emits UTF-8 BOM files for the seven
added languages. Edit the JSON source instead of generated YAML. Semantic review
and static syntax checks do not certify native UI fit or playtesting in every
language. This localization update adds no gameplay coverage to the historical
record below.

## Recorded validation and remaining coverage

The reviewed gameplay code passed **37 static checks** and all three generator
checks on CK3 1.20.0.3. Three isolated engine scenarios on 2026-10-04 passed
**51 assertions**: religious victory over a feudal ruler (20), religious victory
over a tribal ruler (17), and defeat after declining protection followed by the
defender's conversion to the attacker's faith (14). They exercised real native
war start/end callbacks, confirming war-scope access, issued protection, temporary
flag cleanup, continued protection after conversion, feudal 2/1 terms with a
negotiation block, and devotion 3→2 from the declaration snapshot. The fixture
stopped its own game process afterward; this was immediate outcome coverage,
not ordinary combat or a graceful-exit test.

A separate user campaign reviewed on 2026-10-05 confirmed high 3/3 obligations
after the Polish victory and their unchanged serialization in later saves.
Religious protection of a tribal Prussian vassal remained serialized eleven
game days after peace. The user reported that the group UI displayed normally
and requested more header contrast. RC1 used native
`Background_Area_Border_Solid` and `#high` text, but the user subsequently rejected
its appearance because the group was still too dark. RC2 changes only the GUI
presentation: the group header uses button_standard with an explicit clean texture and transparent frames 1-3 in both fold states, opaque bronze/gold fills (folded RGB 0.48/0.36/0.18; unfolded RGB 0.56/0.43/0.23), a gold frame, a #high label, native button_expand_fold_out, and height 44. The user later reported completing RC2 testing and authorized publication.
The supplied screenshots visually confirm the golden expanded header and
Low Obligations victory, defeat and white-peace previews. They do not establish
that these outcomes occurred. Other gameplay files remain unchanged from RC1. The current GUI
SHA-256 is `3184650575871271ff75a4271eb999d229c7eaf97e05e89171018a0ee4b6defe`.

An observed AI refusal-marked defeat coincided with a drop in accumulated piety
between annual saves. That observation does not isolate an exact one-level
change; the isolated native scenario supplies the precise devotion result.
Game logs contained background diagnostics. No whole-log-clean or full-coverage
claim is made. An initialization data-export crash also occurred in an unmodded
control and was not counted as a successful smoke test. The older Tiger 1.19
validator was not a clean validation of these CK3 1.20 scripts.

Remaining coverage includes actual save reload, succession, low/normal profile
victories, remaining defeat/white-peace and inverse faith-change cases, Jizya
branches, exact in-game cost/reparations deductions, longer AI campaigns, and
exhaustive option/tooltip review. Saved state after later
ticks is evidence of persistence, not proof that a reload was executed. Packaging
and source-export checks do not close these gameplay or visual gaps.


## Publication build

`tools/build_publication_pack.py` prepares a localization-only update from an
explicitly supplied published 0.2.0 kit/runtime and reviewed 0.2.1 text/source
staging. Supply an output root, the unchanged approved Paradox JPEG and a mutable
journal path. The builder never starts CK3, changes a launcher, updates a registry
or publishes externally. Existing GAME and deploy directories cannot be replaced.

The clean payload contains 27 files: the original thirteen with a version-only
descriptor change, plus fourteen new translation YAML files. The builder pins the
published baseline and rejects any change to gameplay, GUI, thumbnail or existing
English/Russian localization. The 60-file portable source includes nine JSON
translation sources and the independent language verifier. Assigned platform IDs
are retained; only the Steam descriptor receives `remote_file_id`. Portable manual
wrappers and other platform descriptors remain free of that field. The Paradox
ZIP contains the clean runtime at its root; Nexus includes a mod directory, sibling
wrapper and installation instructions.

`--verify-only` checks both the existing 0.2.0 kit and new 0.2.1 kits, including
source links, input locks, source/runtime identity, platform overlays, archive
members, CRCs and payload hashes. Mutable evidence and publication progress remain
outside immutable packs. Packaging success does not mean the update was uploaded
or downloaded from a public platform.

The final user-session review confirmed that the launcher used the frozen RC2
runtime and recorded a Low Obligations war and normal in-game Quit. The user
reported testing complete. Actual reload and succession remain independently
unverified: the reviewed start save and screenshots are insufficient, and the
new autosaves use a binary format unsupported by the existing audit parser.
No converter or extra game run was used to turn that limitation into a claim.
The gallery preserves the four user captures through JPEG compression only;
its captions explicitly identify previews. Background log diagnostics remain,
so no whole-log-clean claim accompanies publication preparation.
