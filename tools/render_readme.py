"""Render the public README from the canonical player description and gallery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GALLERY = (
    ("01-vassalization-options.jpg", "Choosing vassalization terms"),
    ("02-low-obligations-victory.jpg", "Low Obligations: victory preview"),
    ("03-low-obligations-defeat.jpg", "Low Obligations: defeat preview"),
    ("04-low-obligations-white-peace.jpg", "Low Obligations: white-peace preview"),
)


def render_readme(source: str) -> str:
    gallery = "\n\n".join(
        f"{caption}\n\n![{caption}](publishing/media/gallery/{name})"
        for name, caption in GALLERY
    )
    return (
        "<!-- Generated from publishing/description.en.md; edit the source. -->\n\n"
        + source.rstrip()
        + "\n\n## Screenshots\n\n"
        + gallery
        + "\n\n## Contributing\n\nSee [development notes](dev.md) for implementation details and validation records.\n"
    )


def main() -> None:
    source = (ROOT / "publishing/description.en.md").read_text(encoding="utf-8")
    for name, _ in GALLERY:
        if not (ROOT / "publishing/media/gallery" / name).is_file():
            raise FileNotFoundError(f"Missing gallery image: {name}")
    (ROOT / "README.md").write_bytes(render_readme(source).encode("utf-8"))


if __name__ == "__main__":
    main()
