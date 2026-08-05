from pathlib import Path


def read_version() -> str:
    """Repo-root VERSION file, bumped +0.01 every commit. Path differs between
    the container (/app/VERSION) and local dev (repo root)."""
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "VERSION", here.parents[2] / "VERSION"):
        if candidate.is_file():
            return candidate.read_text().strip()
    return "dev"


VERSION = read_version()
