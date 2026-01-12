import pymysql
import pandas as pd

def test_starrocks_connection():
    try:
        # Connect to StarRocks
        connection = pymysql.connect(
            host='127.0.0.1',
            port=9131,
            user='root',
            password='',
            database='test'  # Connect to test database
        )
        
        cursor = connection.cursor()
        
        # Try to get materialized views from test database
        try:
            cursor.execute("SELECT * FROM information_schema.materialized_views WHERE TABLE_SCHEMA = 'test'")
            test_mv_data = cursor.fetchall()
            print("Test database materialized views:", test_mv_data)
            
            # Get column names for materialized views in test database
            cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_NAME = 'MATERIALIZED_VIEWS' AND TABLE_SCHEMA = 'INFORMATION_SCHEMA'")
            columns = cursor.fetchall()
            print("Materialized Views columns:", columns)
            
        except Exception as e:
            print(f"Error querying test database materialized views: {e}")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Connection error: {e}")

def test_task_runs():
    try:
        # Connect to StarRocks
        connection = pymysql.connect(
            host='127.0.0.1',
            port=9131,
            user='root',
            password='',
            database='information_schema'  # Start with information_schema for task_runs
        )
        
        cursor = connection.cursor()
        
        # Get column names for task_runs
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_NAME = 'TASK_RUNS' AND TABLE_SCHEMA = 'INFORMATION_SCHEMA'")
        task_columns = cursor.fetchall()
        print("Task Runs columns:", task_columns)
        
        # Query specific task runs for any materialized view
        cursor.execute("SELECT * FROM information_schema.task_runs LIMIT 5")
        task_data = cursor.fetchall()
        print("Task Runs sample data:", task_data)
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    print("=== Testing materialized views in test database ===")
    test_starrocks_connection()
    
    print("\n=== Testing task_runs information ===")
    test_task_runs()