# ToyDB

A tiny, document-oriented database optimized for your happiness :)

## Overview

ToyDB is a lightweight, document-oriented database written in pure Python. It provides a simple and intuitive API for storing and querying JSON-like documents. Inspired by [TinyDB](https://github.com/msiemens/tinydb), ToyDB is designed for small-scale applications, prototyping, and learning.

## Features

- **Simple API**: Intuitive Pythonic interface
- **Document-Oriented**: Store any JSON-serializable data
- **Query Language**: Powerful query API with chaining
- **Multiple Storages**: JSON file or in-memory storage
- **Middleware Support**: Extensible with caching, compression, etc.
- **Type Hints**: Full typing support for better IDE experience
- **Zero Dependencies**: Pure Python, no external dependencies for core

## Installation

```bash
pip install toydb
```

Or with Poetry:

```bash
poetry add toydb
```

## Quick Start

```python
from toydb import ToyDB, where

# Create a database
db = ToyDB('data.json')

# Insert documents
db.insert({'type': 'apple', 'count': 7})
db.insert({'type': 'peach', 'count': 3})

# Search documents
results = db.search(where('type') == 'apple')
print(results)  # [{'type': 'apple', 'count': 7, '_id': 1}]

# Update documents
db.update({'count': 10}, where('type') == 'apple')

# Remove documents
db.remove(where('count') < 5)

# Close the database
db.close()
```

## Usage Guide

### Creating a Database

```python
from toydb import ToyDB
from toydb.storages import JSONStorage, MemoryStorage

# With JSON file storage (default)
db = ToyDB('path/to/db.json')
db = ToyDB('path/to/db.json', storage=JSONStorage)

# With in-memory storage (non-persistent)
db = ToyDB(storage=MemoryStorage)

# Using as context manager (auto-closes)
with ToyDB('data.json') as db:
    db.insert({'key': 'value'})
```

### Working with Tables

```python
# Default table (named '_default')
db.insert({'name': 'Alice'})

# Custom tables
users = db.table('users')
products = db.table('products')

# Insert into specific table
users.insert({'name': 'Bob', 'age': 25})
products.insert({'name': 'Laptop', 'price': 999})

# List all tables
print(db.tables())  # {'_default', 'users', 'products'}

# Drop a table
db.drop_table('users')

# Drop all tables
db.drop_tables()
```

### Inserting Documents

```python
# Single document
doc_id = db.insert({'name': 'Alice', 'age': 30})
print(doc_id)  # 1

# Multiple documents
db.insert_multiple([
    {'name': 'Bob', 'age': 25},
    {'name': 'Charlie', 'age': 35}
])

# Document IDs are auto-generated
# Access via '_id' field
```

### Querying Documents

```python
from toydb import where

# Basic comparisons
db.search(where('name') == 'Alice')
db.search(where('age') != 25)
db.search(where('age') > 25)
db.search(where('age') >= 25)
db.search(where('age') < 25)
db.search(where('age') <= 25)

# Logical operations
db.search((where('age') > 25) & (where('age') < 35))  # AND
db.search((where('age') < 25) | (where('age') > 35))  # OR
db.search(~(where('age') > 25))  # NOT

# String operations
db.search(where('name').matches('^A.*'))  # Regex match
db.search(where('name').contains('lic'))  # Substring
db.search(where('email').search(r'@gmail\.com'))  # Regex search

# Collection operations
db.search(where('name').one_of(['Alice', 'Bob']))
db.search(where('tags').has('python'))
db.search(where('scores').any(where('value') > 90))
db.search(where('scores').all(where('value') > 60))

# Nested fields
db.search(where('address.city') == 'NYC')

# Custom test
db.search(where('age').test(lambda x: x % 2 == 0))  # Even ages
```

### Updating Documents

```python
# Update fields
from toydb import where

db.update({'status': 'inactive'}, where('last_login') < '2023-01-01')

# Update with operation
def increment_age(doc):
    doc['age'] += 1

db.update(increment_age, where('name') == 'Alice')

# Update all documents
db.update({'version': 2})
```

### Removing Documents

```python
from toydb import where

# Remove matching documents
db.remove(where('status') == 'inactive')

# Remove all documents
db.truncate()
```

### Storage Backends

#### JSON Storage (Default)

```python
from toydb import ToyDB
from toydb.storages import JSONStorage

db = ToyDB('data.json', storage=JSONStorage)
```

#### Memory Storage

```python
from toydb import ToyDB
from toydb.storages import MemoryStorage

db = ToyDB(storage=MemoryStorage)
# Data is lost when program exits
```

#### Custom Storage

```python
from toydb.storages import Storage

class MyStorage(Storage):
    def read(self):
        # Return dict or None
        pass

    def write(self, data):
        # Persist data dict
        pass

    def close(self):
        # Cleanup
        pass

db = ToyDB(storage=MyStorage)
```

## Advanced Usage

### Middleware

```python
from toydb import ToyDB
from toydb.middlewares import CachingMiddleware
from toydb.storages import JSONStorage

# Add caching layer
db = ToyDB('data.json', storage=CachingMiddleware(JSONStorage))
```

### Document IDs

```python
# Get document ID
doc_id = db.insert({'name': 'Alice'})

# Access by ID
doc = db.get(doc_id)

# Check if exists
if db.contains(doc_id):
    print("Document exists")

# Update by ID
db.update({'status': 'active'}, doc_ids=[doc_id])

# Remove by ID
db.remove(doc_ids=[doc_id])
```

### Counting and Listing

```python
# Count all documents
count = len(db)

# Count matching
count = db.count(where('active') == True)

# Get all documents
all_docs = db.all()

# Iterate over documents
for doc in db:
    print(doc)
```

## API Reference

### ToyDB Class

```python
ToyDB(path, storage=JSONStorage, **kwargs)
```

Methods:
- `table(name)` - Get or create a table
- `tables()` - Get set of table names
- `drop_table(name)` - Remove a table
- `drop_tables()` - Remove all tables
- `close()` - Close the database
- `storage` - Access storage instance

### Table Class

Methods:
- `insert(document)` - Insert a document
- `insert_multiple(documents)` - Insert multiple documents
- `all()` - Get all documents
- `search(cond)` - Search with query
- `get(cond/doc_id)` - Get single document
- `contains(cond/doc_id)` - Check existence
- `count(cond)` - Count documents
- `update(fields, cond)` - Update documents
- `remove(cond)` - Remove documents
- `truncate()` - Remove all documents
- `purge()` - Remove table

### Query Class

Available via `where`:

- `where(field)` - Start a query on field
- `where(field) == value` - Equality
- `where(field) != value` - Inequality
- `where(field) < value` - Less than
- `where(field) > value` - Greater than
- `where(field) <= value` - Less than or equal
- `where(field) >= value` - Greater than or equal
- `where(field).matches(regex)` - Regex match
- `where(field).contains(str)` - Substring
- `where(field).search(regex)` - Regex search
- `where(field).test(func)` - Custom test
- `where(field).one_of(list)` - In list
- `where(field).has(query)` - Has element matching
- `where(field).any(query)` - Any element matches
- `where(field).all(query)` - All elements match

Logical operations:
- `query1 & query2` - AND
- `query1 | query2` - OR
- `~query` - NOT

## Examples

### Todo List

```python
from toydb import ToyDB, where

db = ToyDB('todos.json')
todos = db.table('todos')

# Add todo
todos.insert({
    'title': 'Buy groceries',
    'done': False,
    'priority': 'high'
})

# List pending
pending = todos.search(where('done') == False)

# Mark done
todos.update({'done': True}, where('title') == 'Buy groceries')

# Remove completed
todos.remove(where('done') == True)
```

### Simple Cache

```python
from toydb import ToyDB, where
import time

cache = ToyDB(storage=MemoryStorage)

def get_cached(key, ttl=300):
    result = cache.get(where('key') == key)
    if result and time.time() - result['timestamp'] < ttl:
        return result['value']
    return None

def set_cache(key, value):
    cache.insert({'key': key, 'value': value, 'timestamp': time.time()})
```

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=toydb

# Type checking
pytest --mypy
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## License

MIT License

## Acknowledgments

Inspired by [TinyDB](https://github.com/msiemens/tinydb) by Markus Siemens.
