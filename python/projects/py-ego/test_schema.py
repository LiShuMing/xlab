import pymysql
import pandas as pd

def test_task_runs_schema():
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
        
        # Get column names for task_runs using a different approach
        cursor.execute("DESC information_schema.task_runs")
        columns = cursor.fetchall()
        print("Task Runs columns:", columns)
        
        # Try a simple query to test
        cursor.execute("SELECT * FROM information_schema.task_runs LIMIT 1")
        data = cursor.fetchall()
        print("Sample data:", data)
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    test_task_runs_schema()