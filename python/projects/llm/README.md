# StarRocks Materialized View Monitor

A comprehensive monitoring and visualization tool for StarRocks materialized views that provides real-time insights into refresh status, history, and performance metrics.

## Features

- **Real-time Monitoring**: Monitor the status of all materialized views in your StarRocks cluster
- **Refresh History**: Track historical refresh operations with detailed information
- **Performance Metrics**: View refresh duration, success rates, and performance trends
- **Visual Analytics**: Charts and graphs for better insights into MV performance
- **Extensible Architecture**: Easy to extend for additional monitoring capabilities

## Architecture

The solution is built with a modular, extensible architecture:

### Core Components

1. **StarRocksBaseMonitor**: Abstract base class for all monitoring operations
2. **MaterializedViewMonitor**: Handles MV-specific monitoring
3. **TaskRunMonitor**: Handles refresh history monitoring
4. **StarRocksMVMonitor**: Main class that combines all monitoring capabilities
5. **Streamlit UI**: Interactive web interface

### Extensibility Points

The system is designed to be easily extensible:

1. **New Monitor Classes**: Create additional monitor classes by inheriting from `StarRocksBaseMonitor`
2. **Custom Queries**: Extend monitoring with custom SQL queries
3. **Additional Visualizations**: Add new charts and graphs in the Streamlit UI
4. **Export Capabilities**: Add functionality to export monitoring data

## Setup

### Prerequisites

- Python 3.8+
- StarRocks instance with access to information_schema

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Update the connection parameters in the UI or code:
- Host: StarRocks host (default: 127.0.0.1)
- Port: StarRocks port (default: 9131)
- User: Database user (default: root)
- Password: Database password (default: empty)

## Usage

### Running the Application

```bash
streamlit run streamlit_mv_monitor.py
```

### Key Functionality

1. **Overview Dashboard**: High-level summary of materialized view status
2. **Materialized Views**: Detailed view of all MVs with filtering capabilities
3. **Refresh History**: Timeline of refresh operations for selected MVs
4. **Performance Metrics**: Detailed statistics on refresh performance

## Extending the Solution

### Adding New Monitor Types

To add a new type of monitor, inherit from `StarRocksBaseMonitor`:

```python
class CustomMonitor(StarRocksBaseMonitor):
    def get_data(self, **kwargs) -> pd.DataFrame:
        query = "SELECT * FROM information_schema.custom_table"
        return self.execute_query(query)
    
    def transform_data(self, df: pd.DataFrame) -> pd.DataFrame:
        # Transform the data as needed
        return df
```

### Adding New Visualizations

New tabs can be easily added to the Streamlit UI:

```python
with st.tabs(["Overview", "Materialized Views", "Refresh History", "Custom Tab"]):
    # Add your new visualization in the corresponding tab
```

### Configuration Options

The monitoring system can be extended with:
- Different time ranges for analysis
- Custom alert thresholds
- Export options for different formats
- Integration with monitoring platforms

## Database Schema Access

The application queries the following information_schema tables:
- `information_schema.materialized_views` - MV definitions and status
- `information_schema.task_runs` - Refresh operation history

## Contributing

To extend the monitoring capabilities:
1. Create new monitor classes by extending the base class
2. Add new visualization in the Streamlit UI
3. Update the main monitor class to include your new functionality
4. Test with your StarRocks environment

## Troubleshooting

- Make sure StarRocks is running and accessible
- Verify user has sufficient permissions to query information_schema
- Check connection parameters in the UI

For additional metrics and monitoring capabilities, refer to the StarRocks documentation:
- https://docs.starrocks.io/docs/administration/management/monitoring/metrics-materialized_view/
- https://docs.starrocks.io/docs/sql-reference/sql-statements/materialized_view/SHOW_MATERIALIZED_VIEW/
- https://docs.starrocks.io/docs/sql-reference/information_schema/task_runs/