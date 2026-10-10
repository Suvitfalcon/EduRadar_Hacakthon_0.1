import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
_tmp = tempfile.mkdtemp()
pd.read_csv(ROOT / "student_support_10000.csv").head(400).to_csv(Path(_tmp) / "small.csv", index=False)
os.environ["EDURADAR_DB"] = str(Path(_tmp) / "test.db")
os.environ["EDURADAR_SEED_CSV"] = str(Path(_tmp) / "small.csv")


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from backend.main import app
    with TestClient(app) as c:
        yield c
