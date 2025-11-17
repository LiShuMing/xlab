#!/usr/bin/env python3
"""
Parse slow_lock.log file and find lock owners with type WRITE
"""

import json
import sys
from collections import defaultdict

def parse_slow_lock_log(file_path):
    """
    Parse slow_lock.log file and find lock owners with type WRITE
    
    Args:
        file_path (str): Path to the slow_lock.log file
        
    Returns:
        list: List of WRITE lock entries with their details
    """
    write_locks = []
    line_count = 0
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line_count += 1
                # Skip empty lines
                if not line.strip():
                    continue
                
                try:
                    # Extract JSON part from log line
                    # Log format: TIMESTAMP WARN (THREAD_INFO) [CLASS.METHOD():LINE] MESSAGE : JSON_DATA
                    if ':' in line:
                        parts = line.split(':', 4)  # Split into at most 5 parts
                        if len(parts) >= 5:
                            json_part = parts[4].strip()
                            if json_part.startswith('{'):
                                # Parse JSON from the log line
                                log_data = json.loads(json_part)
                                
                                # Extract owners and waiters
                                owners = log_data.get('owners', [])
                                waiters = log_data.get('waiter', [])
                                
                                # Check for WRITE locks in owners
                                for owner in owners:
                                    if owner.get('type') == 'WRITE':
                                        write_locks.append({
                                            'line_number': line_count,
                                            'lock_info': log_data,
                                            'lock_owner': owner,
                                            'thread_info': extract_thread_info(parts[2]) if len(parts) > 2 else None
                                        })
                                        
                                # Check for WRITE locks in waiters
                                for waiter in waiters:
                                    if waiter.get('type') == 'WRITE':
                                        write_locks.append({
                                            'line_number': line_count,
                                            'lock_info': log_data,
                                            'lock_waiter': waiter,
                                            'thread_info': extract_thread_info(parts[2]) if len(parts) > 2 else None
                                        })
                except json.JSONDecodeError:
                    # Skip lines that don't contain valid JSON
                    continue
                    
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return []
    except Exception as e:
        print(f"Error reading file: {e}")
        return []
    
    return write_locks

def extract_thread_info(thread_part):
    """
    Extract thread information from the log line
    
    Args:
        thread_part (str): The thread information part of the log line
        
    Returns:
        dict: Parsed thread information
    """
    # Format: (thread_name|thread_id)
    if '|' in thread_part:
        name_part, id_part = thread_part.split('|')
        return {
            'name': name_part.strip('() '),
            'id': id_part.strip()
        }
    return {'name': thread_part.strip('() '), 'id': None}

def print_write_locks(write_locks):
    """
    Print WRITE lock information
    
    Args:
        write_locks (list): List of WRITE lock entries
    """
    if not write_locks:
        print("No WRITE locks found.")
        return
    
    print(f"Found {len(write_locks)} WRITE locks:")
    print("=" * 50)
    
    # Group by lock owner ID for better organization
    locks_by_owner = defaultdict(list)
    for lock in write_locks:
        owner_id = lock.get('lock_owner', {}).get('id') or lock.get('lock_waiter', {}).get('id')
        locks_by_owner[owner_id].append(lock)
    
    for owner_id, locks in locks_by_owner.items():
        owner_name = locks[0].get('lock_owner', {}).get('name') or locks[0].get('lock_waiter', {}).get('name')
        print(f"\nOwner ID: {owner_id} ({owner_name})")
        print("-" * 30)
        
        for lock in locks:
            line_num = lock['line_number']
            lock_type = 'OWNER' if 'lock_owner' in lock else 'WAITER'
            lock_details = lock.get('lock_owner') or lock.get('lock_waiter')
            
            print(f"  Line {line_num} ({lock_type}):")
            print(f"    Type: {lock_details.get('type')}")
            print(f"    Wait Time: {lock_details.get('waitTime', 'N/A')} ms")
            if 'heldFor' in lock_details:
                print(f"    Held For: {lock_details.get('heldFor')} ms")
                
            thread_info = lock.get('thread_info')
            if thread_info:
                print(f"    Thread: {thread_info.get('name')} | {thread_info.get('id')}")
            
            # Print stack trace if available
            if 'stack' in lock_details:
                print("    Stack Trace:")
                for i, stack_line in enumerate(lock_details['stack'][:5]):  # Show first 5 lines
                    print(f"      {stack_line}")
                if len(lock_details['stack']) > 5:
                    print(f"      ... and {len(lock_details['stack']) - 5} more")

def main():
    file_path = "slow_lock.log"
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    
    print(f"Parsing {file_path} for WRITE locks...")
    
    write_locks = parse_slow_lock_log(file_path)
    print_write_locks(write_locks)

if __name__ == "__main__":
    main()