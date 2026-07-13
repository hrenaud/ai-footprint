#!/usr/bin/env python3
"""Régénère docs/guide/ (FR + EN) à partir des Markdown de docs/ via mkdocs.

GitHub Pages sert docs/ tel quel (pas de build côté serveur) : ce script
doit être relancé et son résultat commité à chaque changement d'un des
Markdown listés dans mkdocs.yml.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GUIDE_DIR = REPO_ROOT / "docs" / "guide"


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--clean",
                "-f",
                str(REPO_ROOT / "mkdocs.yml"),
                "-d",
                tmp,
            ],
            cwd=REPO_ROOT,
            check=True,
        )
        shutil.rmtree(GUIDE_DIR, ignore_errors=True)
        shutil.copytree(tmp, GUIDE_DIR)
    print(f"Site généré dans {GUIDE_DIR}")


if __name__ == "__main__":
    main()
