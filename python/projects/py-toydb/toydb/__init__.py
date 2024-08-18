"""
ToyDB is a tiny, document oriented database optimized for your happiness :)

ToyDB stores different types of Python data types using a configurable
storage mechanism. It comes with a syntax for querying data and storing
data in multiple tables.
Usage example:

>>> from toydb import ToyDB, where
>>> from toydb.storages import MemoryStorage
>>> db = ToyDB(storage=MemoryStorage)
>>> db.insert({'data': 5})  # Insert into '_default' table
>>> db.search(where('data') == 5)
[{'data': 5, '_id': 1}]
>>> # Now let's create a new table
>>> tbl = db.table('our_table')
>>> for i in range(10):
...     tbl.insert({'data': i})
...
>>> len(tbl.search(where('data') < 5))
5
"""

from .queries import Query, where
from .storages import Storage, JSONStorage
from .db import ToyDB
from .version import __version__

__all__ = ('ToyDB', 'Storage', 'JSONStorage', 'Query', 'where')
