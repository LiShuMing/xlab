import json
import sys

def parse_slow_lock_log(file_path):
    """
    Parse slow_lock.log file and find lock owners with type WRITE
    
    Args:
        file_path (str): Path to the slow_lock.log file
    """
    write_locks = []
    
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
                    
                    # Check if the lock type is WRITE
                    if log_entry.get('type') == 'WRITE':
                        write_locks.append({
                            'line_number': line_number,
                            'lock_owner': log_entry.get('owner'),
                            'lock_type': log_entry.get('type'),
                            'timestamp': log_entry.get('timestamp'),
                            'details': log_entry
                        })
                        
                except json.JSONDecodeError as e:
                    print(f"Warning: Invalid JSON on line {line_number}: {e}")
                    continue
                    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
    return write_locks

def main():
    file_path = "slow_lock.log"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    print(f"Parsing {file_path} for WRITE locks...")
    
    write_locks = parse_slow_lock_log(file_path)
    
    if not write_locks:
        print("No WRITE locks found or error occurred.")
        return
    
    print(f"\nFound {len(write_locks)} WRITE locks:")
    print("-" * 50)
    
    for lock in write_locks:
        print(f"Line {lock['line_number']}:")
        print(f"  Owner: {lock['lock_owner']}")
        print(f"  Type: {lock['lock_type']}")
        print(f"  Timestamp: {lock['timestamp']}")
        print()

if __name__ == "__main__":
    main()