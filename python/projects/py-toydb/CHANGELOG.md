# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Query result pagination
- Index support for faster queries
- More storage backends (YAML, MessagePack)
- Async storage support
- Query optimization

## [4.8.2] - 2024-XX-XX

### Added
- Type hints for all public APIs
- Full mypy support
- Improved IDE autocomplete support via `with_typehint`

### Changed
- Updated minimum Python version to 3.8
- Improved documentation

### Fixed
- Various typing issues

## [4.8.0] - 2024-XX-XX

### Added
- Context manager support for ToyDB
  ```python
  with ToyDB('data.json') as db:
      db.insert({'key': 'value'})
  # Auto-closes on exit
  ```

### Changed
- Improved storage backend interface
- Better error messages

## [4.7.0] - 2024-XX-XX

### Added
- Middleware system for storage
  - CachingMiddleware for in-memory caching
  - Easy to extend with custom middleware

### Fixed
- Race condition in table caching

## [4.6.0] - 2024-XX-XX

### Added
- New query operations
  - `has()` - Check if field has matching element
  - `any()` - Check if any element matches
  - `all()` - Check if all elements match
- Better support for nested document queries

## [4.5.0] - 2023-XX-XX

### Added
- Table.drop() method for removing tables
- Performance improvements for large datasets

### Changed
- Optimized query evaluation

## [4.4.0] - 2023-XX-XX

### Added
- Query test() method for custom queries
  ```python
  db.search(where('age').test(lambda x: x % 2 == 0))
  ```

### Fixed
- Bug with updating nested documents

## [4.3.0] - 2023-XX-XX

### Added
- Document ID access in search results
- Better document iteration support

### Changed
- Improved repr() output for ToyDB and Table

## [4.2.0] - 2023-XX-XX

### Added
- Query regex support
  - `matches()` - Match regex pattern
  - `search()` - Search for regex pattern
- String contains query
  ```python
  db.search(where('name').contains('lic'))
  ```

## [4.1.0] - 2023-XX-XX

### Added
- Document insertion returns document ID
- Multiple document insertion
  ```python
  db.insert_multiple([doc1, doc2, doc3])
  ```

### Fixed
- JSONStorage file locking issues

## [4.0.0] - 2023-XX-XX

### Added
- Complete rewrite with modern Python features
- Type hints throughout
- Poetry for dependency management
- Comprehensive test suite with pytest
- pycodestyle checking
- mypy type checking

### Changed
- **BREAKING**: New import structure
  ```python
  from toydb import ToyDB, where
  from toydb.storages import JSONStorage, MemoryStorage
  ```
- **BREAKING**: Storage interface changed
- Improved API consistency

### Removed
- **BREAKING**: Dropped Python 2 support
- **BREAKING**: Removed deprecated APIs

## [3.15.2] - 2022-XX-XX

### Fixed
- Last version before 4.0 rewrite
- Various bug fixes

## [3.0.0] - 2020-XX-XX

### Added
- Python 3 support
- Query API improvements

## [2.0.0] - 2018-XX-XX

### Added
- Major API improvements
- Better documentation

## [1.0.0] - 2013-XX-XX

### Added
- Initial release
- Basic document storage
- Query API
- JSON storage backend
