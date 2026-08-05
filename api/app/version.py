from pathlib import Path


def read_version() -> str:
    """Repo-root VERSION file, bumped +0.01 every commit. Path differs between
    the container (/app/VERSION) and local dev (repo root)."""
    here = Path(__file__).resolve()
    for candidate in (here.parents[1] / "VERSION", here.parents[2] / "VERSION"):
        if candidate.is_file():
            # utf-8-sig drops a byte-order mark if an editor left one — it is
            # invisible in the file but shows up in the version string and, far
            # worse, in the image tag CI builds from it
            return candidate.read_text(encoding="utf-8-sig").strip()
    return "dev"


VERSION = read_version()
