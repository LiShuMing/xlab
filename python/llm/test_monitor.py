import pandas as pd
from starrocks_mv_monitor import StarRocksMVMonitor


def test_monitoring():
    print("Testing StarRocks Materialized View Monitor...")
    
    # Initialize monitor
    monitor = StarRocksMVMonitor(host='127.0.0.1', port=9131, user='root', password='')
    
    # Connect to StarRocks
    if not monitor.connect():
        print("Failed to connect to StarRocks")
        return
    
    print("Connected to StarRocks successfully!")
    
    # Test getting materialized views
    print("\n--- Testing Materialized Views ---")
    mv_data = monitor.get_materialized_views()
    print(f"Found {len(mv_data)} materialized views")
    if not mv_data.empty:
        print("Columns:", list(mv_data.columns))
        print("Sample data:")
        print(mv_data.head())
    
    # Test getting task runs
    print("\n--- Testing Task Runs ---")
    task_data = monitor.get_task_runs(limit=10)
    print(f"Found {len(task_data)} task runs")
    if not task_data.empty:
        print("Columns:", list(task_data.columns))
        print("Sample data:")
        print(task_data.head())
    
    # Test getting refresh history for a specific task (if any exist)
    print("\n--- Testing Refresh History ---")
    if not mv_data.empty:
        # Get the first materialized view ID to test
        mv_id = str(mv_data.iloc[0]['mv_id'])
        history_data = monitor.get_refresh_history(mv_id=mv_id, days=30)
        print(f"Found {len(history_data)} history records for MV ID {mv_id}")
        if not history_data.empty:
            print("Sample history data:")
            print(history_data.head())
    
    # Test getting statistics
    print("\n--- Testing Statistics ---")
    stats = monitor.get_mv_statistics()
    print("Statistics:", stats)
    
    # Test getting refresh status summary
    print("\n--- Testing Refresh Status Summary ---")
    summary = monitor.get_refresh_status_summary(days=7)
    print(f"Found {len(summary)} summary records")
    if not summary.empty:
        print("Sample summary data:")
        print(summary.head())
    
    # Test getting performance metrics
    print("\n--- Testing Performance Metrics ---")
    perf_metrics = monitor.get_refresh_performance_metrics(days=30)
    print(f"Found {len(perf_metrics)} performance metric records")
    if not perf_metrics.empty:
        print("Sample performance data:")
        print(perf_metrics.head())
    
    # Disconnect
    monitor.disconnect()
    print("\nDisconnected from StarRocks")


if __name__ == "__main__":
    test_monitoring()
