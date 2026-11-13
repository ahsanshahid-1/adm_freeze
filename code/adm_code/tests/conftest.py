import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adm.core import Paths  # noqa: E402
from adm import datasets as D  # noqa: E402


@pytest.fixture(scope="session")
def paths(tmp_path_factory):
    root = tmp_path_factory.mktemp("adm")
    p = Paths(root / "state", root / "cache", root / "models").ensure()
    D.build_canonical(p, include_public=False)
    D.build_splits(p, "development", ["D5", "D6"], [0, 1, 2])
    return p
