import pymysql
import pandas as pd
from datetime import datetime, timedelta
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class StarRocksBaseMonitor(ABC):
    """
    Abstract base class for StarRocks monitoring that provides common functionality
    and can be extended for different monitoring purposes.
    """
    
    def __init__(self, host: str = '127.0.0.1', port: int = 9131, user: str = 'root', password: str = ''):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.connection = None
    
    def connect(self):
        """Establish connection to StarRocks"""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database='information_schema'
            )
            return True
        except Exception as e:
            st.error(f"Connection error: {e}")
            return False
    
    def disconnect(self):
        """Close connection to StarRocks"""
        if self.connection:
            self.connection.close()
    
    @abstractmethod
    def get_data(self, **kwargs) -> pd.DataFrame:
        """Abstract method to fetch monitoring data"""
        pass
    
    @abstractmethod
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Abstract method to transform raw data into a standardized format"""
        pass
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a DataFrame"""
        try:
            cursor = self.connection.cursor()
            cursor.execute(query)
            result = cursor.fetchall()
            
            # Get column names
            columns = [desc[0] for desc in cursor.description]
            cursor.close()
            
            # Convert to DataFrame
            df = pd.DataFrame(result, columns=columns)
            return df
        except Exception as e:
            print(f"Query execution error: {e}")
            return pd.DataFrame()


class MaterializedViewMonitor(StarRocksBaseMonitor):
    """
    Monitor for StarRocks materialized views
    """
    
    def get_data(self, database_name: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch materialized views data from information_schema
        """
        if database_name:
            query = f"""
            SELECT * FROM information_schema.materialized_views 
            WHERE TABLE_SCHEMA = '{database_name}'
            """
        else:
            query = "SELECT * FROM information_schema.materialized_views"
        
        return self.execute_query(query)
    
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform raw materialized views data into a standardized format
        """
        # Convert timestamp columns to datetime if they exist
        timestamp_cols = ['created_time', 'last_refresh_started', 'last_refresh_finished', 'last_accessed']
        for col in timestamp_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        
        return df


class TaskRunMonitor(StarRocksBaseMonitor):
    """
    Monitor for StarRocks task runs (refresh history)
    """
    
    def get_data(self, task_name: Optional[str] = None, limit: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch task runs data from information_schema
        """
        query = "SELECT * FROM information_schema.task_runs"
        
        conditions = []
        if task_name:
            conditions.append(f"TASK_NAME = '{task_name}'")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY CREATE_TIME DESC"
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute_query(query)
    
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform raw task runs data into a standardized format
        """
        # Rename columns to more user-friendly names and maintain backward compatibility
        column_mapping = {
            'QUERY_ID': 'query_id',
            'TASK_NAME': 'task_name', 
            'CREATE_TIME': 'start_time',
            'FINISH_TIME': 'end_time',
            'STATE': 'state',
            'CATALOG': 'catalog',
            'DATABASE': 'database_name',
            'DEFINITION': 'definition',
            'EXPIRE_TIME': 'expire_time',
            'ERROR_CODE': 'error_code',
            'ERROR_MESSAGE': 'error_message',
            'PROGRESS': 'progress',
            'EXTRA_MESSAGE': 'extra_message',
            'PROPERTIES': 'properties',
            'JOB_ID': 'job_id',
            'PROCESS_TIME': 'process_time'
        }
        
        # Rename columns that exist
        rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
        df = df.rename(columns=rename_dict)
        
        # Convert timestamp columns to datetime
        if 'start_time' in df.columns:
            df['start_time'] = pd.to_datetime(df['start_time'], errors='coerce')
        if 'end_time' in df.columns:
            df['end_time'] = pd.to_datetime(df['end_time'], errors='coerce')
        
        # Calculate duration if start and end time exist
        if 'start_time' in df.columns and 'end_time' in df.columns:
            df['duration_seconds'] = (df['end_time'] - df['start_time']).dt.total_seconds()
        
        return df


class StarRocksMVMonitor:
    """
    Main monitoring class that brings together materialized view and task run monitoring
    """
    
    def __init__(self, host: str = '127.0.0.1', port: int = 9131, user: str = 'root', password: str = ''):
        self.mv_monitor = MaterializedViewMonitor(host, port, user, password)
        self.task_monitor = TaskRunMonitor(host, port, user, password)
    
    def connect(self):
        """Connect to StarRocks"""
        return self.mv_monitor.connect() and self.task_monitor.connect()
    
    def disconnect(self):
        """Disconnect from StarRocks"""
        self.mv_monitor.disconnect()
        self.task_monitor.disconnect()
    
    def get_materialized_views(self, database_name: Optional[str] = None) -> pd.DataFrame:
        """Get materialized views data"""
        raw_data = self.mv_monitor.get_data(database_name)
        return self.mv_monitor.transform_data(raw_data)
    
    def get_task_runs(self, task_name: Optional[str] = None, limit: Optional[int] = 100) -> pd.DataFrame:
        """Get task runs data"""
        raw_data = self.task_monitor.get_data(task_name, limit)
        return self.task_monitor.transform_data(raw_data)
    
    def get_refresh_history(self, mv_id: Optional[str] = None, task_name: Optional[str] = None, 
                           days: int = 30) -> pd.DataFrame:
        """Get refresh history within a specified time period"""
        start_date = datetime.now() - timedelta(days=days)
        start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if task_name:
            query = f"""
            SELECT * FROM information_schema.task_runs 
            WHERE TASK_NAME = '{task_name}' 
            AND CREATE_TIME >= '{start_date_str}'
            ORDER BY CREATE_TIME DESC
            """
        elif mv_id:
            # Assuming mv_id is part of the task_name format (e.g., mv-12345)
            query = f"""
            SELECT * FROM information_schema.task_runs 
            WHERE TASK_NAME = 'mv-{mv_id}' 
            AND CREATE_TIME >= '{start_date_str}'
            ORDER BY CREATE_TIME DESC
            """
        else:
            query = f"""
            SELECT * FROM information_schema.task_runs 
            WHERE CREATE_TIME >= '{start_date_str}'
            ORDER BY CREATE_TIME DESC
            """
        
        raw_data = self.task_monitor.execute_query(query)
        return self.task_monitor.transform_data(raw_data)
    
    def get_mv_statistics(self) -> Dict[str, Any]:
        """Get overall statistics about materialized views"""
        mv_data = self.get_materialized_views()
        
        stats = {
            'total_mvs': len(mv_data),
            'refresh_success_rate': 0.0,
            'avg_refresh_duration': 0.0
        }
        
        if len(mv_data) > 0:
            # Count status distribution
            if 'last_refresh_state' in mv_data.columns:
                status_counts = mv_data['last_refresh_state'].value_counts()
                if 'SUCCESS' in status_counts:
                    stats['refresh_success_rate'] = status_counts['SUCCESS'] / len(mv_data) * 100
            
            # Calculate average refresh duration if available
            if 'refresh_latency' in mv_data.columns:
                avg_duration = mv_data['refresh_latency'].mean()
                if not pd.isna(avg_duration):
                    stats['avg_refresh_duration'] = avg_duration
        
        return stats

    def get_refresh_status_summary(self, days: int = 7) -> pd.DataFrame:
        """Get summary of refresh status for the last N days"""
        start_date = datetime.now() - timedelta(days=days)
        history_data = self.get_refresh_history(days=days)
        
        if history_data.empty:
            return pd.DataFrame()
        
        # Group by date and status
        if 'start_time' in history_data.columns and 'state' in history_data.columns:
            history_data['date'] = history_data['start_time'].dt.date
            summary = history_data.groupby(['date', 'state']).size().reset_index(name='count')
        else:
            summary = pd.DataFrame()
        
        return summary

    def get_refresh_performance_metrics(self, days: int = 30) -> pd.DataFrame:
        """Get performance metrics for refresh operations"""
        history_data = self.get_refresh_history(days=days)
        
        if history_data.empty or 'duration_seconds' not in history_data.columns:
            return pd.DataFrame()
        
        # Calculate performance metrics
        perf_metrics = history_data.groupby('task_name').agg({
            'duration_seconds': ['mean', 'min', 'max', 'std'],
            'state': lambda x: (x == 'SUCCESS').sum() / len(x) * 100  # Success rate
        }).round(2)
        
        # Flatten column names
        perf_metrics.columns = ['avg_duration', 'min_duration', 'max_duration', 'std_duration', 'success_rate']
        perf_metrics = perf_metrics.reset_index()
        
        return perf_metrics