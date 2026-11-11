"""Curriculum integrity checks.

These keep 180 lessons consistent as they are written one per day: every lesson carries
the frontmatter the template defines, filenames agree with that frontmatter, every lesson
is indexed in the README, and no relative link anywhere in the repo points at nothing.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LESSONS_DIR = ROOT / "docs" / "days"
LESSONS = sorted(LESSONS_DIR.glob("day-[0-9][0-9][0-9]-*.md"))

REQUIRED_KEYS = {
    "day", "phase", "week", "title", "slug", "mode", "duration_min", "concept_min",
    "practical_min", "capstone_version", "deliverable", "tags", "prerequisites",
    "produces", "objectives",
}  # fmt: skip
MODES = {"learn", "build", "consolidate"}
SKIP_DIRS = {".git", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", ".next"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"^```.*?^```", re.S | re.M)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, f"{path.name}: missing YAML frontmatter"
    return yaml.safe_load(match.group(1))


def markdown_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.md") if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
    )


def test_lessons_exist():
    assert LESSONS, "no lessons found in docs/days/"


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.stem)
def test_lesson_frontmatter(lesson: Path):
    fm = frontmatter(lesson)
    missing = REQUIRED_KEYS - fm.keys()
    assert not missing, f"missing keys: {sorted(missing)}"

    assert fm["slug"] == lesson.stem, "slug must equal the filename"
    assert lesson.stem.startswith(f"day-{fm['day']:03d}-"), "day must match the filename"
    assert fm["mode"] in MODES, f"mode must be one of {sorted(MODES)}"
    assert fm["concept_min"] + fm["practical_min"] == fm["duration_min"]
    assert all(p < fm["day"] for p in fm["prerequisites"]), "prerequisites must be earlier days"
    assert fm["objectives"] and all(fm["objectives"]), "objectives must be non-empty"


@pytest.mark.parametrize("lesson", LESSONS, ids=lambda p: p.stem)
def test_lesson_indexed_in_readme(lesson: Path):
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"docs/days/{lesson.name}" in readme, "add this lesson to README 'Lessons written'"


@pytest.mark.parametrize("md", markdown_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(md: Path):
    text = INLINE_CODE_RE.sub("", FENCE_RE.sub("", md.read_text(encoding="utf-8")))
    broken = []
    for target in LINK_RE.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        path = target.split("#", 1)[0]
        if path and not (md.parent / path).exists():
            broken.append(target)
    assert not broken, f"broken links: {broken}"
