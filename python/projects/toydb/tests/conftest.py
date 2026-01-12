import os.path
import tempfile
from pathlib import Path

import pytest  # type: ignore

from toydb.middlewares import CachingMiddleware
from toydb.storages import MemoryStorage
from toydb import ToyDB, JSONStorage

@pytest.fixture(params=['memory', 'json'])
def db(request, tmp_path: Path):
    if request.param == 'json':
        db_ = ToyDB(tmp_path / 'test.db', storage=JSONStorage)
    else:
        db_ = ToyDB(storage=MemoryStorage)

    db_.drop_tables()
    db_.insert_multiple({'int': 1, 'char': c} for c in 'abc')

    yield db_


@pytest.fixture
def storage():
    return CachingMiddleware(MemoryStorage)()
