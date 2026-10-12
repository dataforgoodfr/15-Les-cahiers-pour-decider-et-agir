"""Le découpage de l'outil d'annotation (JavaScript), testé avec Node s'il est là."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node absent")
def test_decoupage_js():
    dossier = Path(__file__).parent / "js"
    sortie = subprocess.run(
        ["node", "--test", *sorted(str(f) for f in dossier.glob("*.test.js"))],
        capture_output=True,
        check=False,
        text=True,
    )
    assert sortie.returncode == 0, sortie.stdout + sortie.stderr
