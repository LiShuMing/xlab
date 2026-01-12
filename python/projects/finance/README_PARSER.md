# Slow Lock Log Parser

This directory contains Python scripts to parse `slow_lock.log` files and extract information about lock owners, particularly those with WRITE locks.

## Files

1. `parse_slow_lock_log.py` - Basic parser that finds all WRITE locks
2. `parse_slow_lock_log_advanced.py` - Advanced parser with filtering options

## Usage

### Basic Parser

```bash
python parse_slow_lock_log.py [path_to_slow_lock.log]
```

If no file path is provided, it defaults to `slow_lock.log` in the current directory.

### Advanced Parser

```bash
# Find all WRITE locks (default)
python parse_slow_lock_log_advanced.py [path_to_slow_lock.log]

# Find locks of a specific type
python parse_slow_lock_log_advanced.py --type READ [path_to_slow_lock.log]

# Show statistics for all lock types
python parse_slow_lock_log_advanced.py --all-types [path_to_slow_lock.log]
```

## Output

The scripts will output:
- Line numbers where WRITE locks were found
- Lock owners
- Timestamps
- Additional details about each lock

The advanced parser also shows:
- Top 10 lock owners
- Statistics for all lock types when using `--all-types`