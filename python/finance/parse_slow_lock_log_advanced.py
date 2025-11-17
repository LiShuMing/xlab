import json
import sys
import argparse
from collections import Counter

def parse_slow_lock_log(file_path, lock_type_filter=None):
    """
    Parse slow_lock.log file and find lock owners with specified type
    
    Args:
        file_path (str): Path to the slow_lock.log file
        lock_type_filter (str): Specific lock type to filter (e.g., 'WRITE')
        
    Returns:
        list: List of matching lock entries
    """
    matching_locks = []
    lock_type_counter = Counter()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            line_number = 0
            for line in file:
                line_number += 1
                try:
                    # Skip empty lines
                    if not line.strip():
                        continue
                    
                    # Parse JSON from each line
                    log_entry = json.loads(line.strip())
                    
                    # Count all lock types
                    lock_type = log_entry.get('type')
                    if lock_type:
                        lock_type_counter[lock_type] += 1
                    
                    # Filter by lock type if specified
                    if lock_type_filter is None or lock_type == lock_type_filter:
                        matching_locks.append({
                            'line_number': line_number,
                            'lock_owner': log_entry.get('owner'),
                            'lock_type': lock_type,
                            'timestamp': log_entry.get('timestamp'),
                            'details': log_entry
                        })
                        
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON on line {line_number}: {e}")
                    continue
                    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return [], Counter()
    except Exception as e:
        print(f"Error reading file: {e}")
        return [], Counter()
    
    return matching_locks, lock_type_counter

def main():
    parser = argparse.ArgumentParser(description='Parse slow_lock.log file and find lock owners')
    parser.add_argument('file_path', nargs='?', default='slow_lock.log', 
                        help='Path to the slow_lock.log file (default: slow_lock.log)')
    parser.add_argument('--type', dest='lock_type', default='WRITE',
                        help='Lock type to filter (default: WRITE)')
    parser.add_argument('--all-types', action='store_true',
                        help='Show all lock types and their counts')
    
    args = parser.parse_args()
    
    print(f"Parsing {args.file_path}...")
    
    # If --all-types flag is set, show statistics for all lock types
    if args.all_types:
        _, lock_type_counter = parse_slow_lock_log(args.file_path)
        print("\nLock Type Statistics:")
        print("-" * 30)
        for lock_type, count in lock_type_counter.most_common():
            print(f"{lock_type}: {count}")
        return
    
    # Otherwise, filter by specified lock type
    matching_locks, lock_type_counter = parse_slow_lock_log(args.file_path, args.lock_type)
    
    if not matching_locks:
        print(f"No {args.lock_type} locks found or error occurred.")
        return
    
    print(f"\nFound {len(matching_locks)} {args.lock_type} locks:")
    print("-" * 50)
    
    # Show top 10 unique lock owners
    owners = [lock['lock_owner'] for lock in matching_locks if lock['lock_owner']]
    owner_counts = Counter(owners)
    
    print(f"Top 10 {args.lock_type} lock owners:")
    for owner, count in owner_counts.most_common(10):
        print(f"  {owner}: {count} locks")
    
    print("\nAll matching entries:")
    for lock in matching_locks:
        print(f"Line {lock['line_number']}:")
        print(f"  Owner: {lock['lock_owner']}")
        print(f"  Type: {lock['lock_type']}")
        print(f"  Timestamp: {lock['timestamp']}")
        print()

if __name__ == "__main__":
    main()