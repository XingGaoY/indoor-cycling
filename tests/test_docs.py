"""Keep the ordered documentation set and relative Markdown links usable."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = [ROOT / "README.md", *sorted((ROOT / "doc").glob("*.md"))]

def test_expected_documentation():
    assert len(DOCS) == 11
    assert [p.name[:2] for p in DOCS[1:]] == [f"{i:02d}" for i in range(1, 11)]
    assert all(p.is_file() for p in DOCS)

def test_relative_markdown_links():
    for document in DOCS:
        source = document.read_text(encoding="utf-8")
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", source):
            if target.startswith(("http:", "https:", "#", "mailto:")):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            assert path.is_file(), f"{document.relative_to(ROOT)} has broken link: {target}"

def test_deployment_scripts_exist():
    for name in ("run-local.sh", "install-launch-agent.sh", "uninstall-launch-agent.sh"):
        assert (ROOT / "scripts" / "macos" / name).is_file()
