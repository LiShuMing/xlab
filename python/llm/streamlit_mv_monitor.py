import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from starrocks_mv_monitor import StarRocksMVMonitor

# Page configuration
st.set_page_config(
    page_title="StarRocks Materialized View Monitor",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'monitor' not in st.session_state:
    st.session_state.monitor = StarRocksMVMonitor()

# Sidebar configuration
st.sidebar.title(" 🌟 StarRocks MV Monitor Configuration")
host = st.sidebar.text_input("Host", value="127.0.0.1")
port = st.sidebar.number_input("Port", value=9131, min_value=1, max_value=65535, step=1)
user = st.sidebar.text_input("User", value="root")
password = st.sidebar.text_input("Password", type="password", value="")

# Connect button
if st.sidebar.button("🔗 Connect to StarRocks"):
    st.session_state.monitor = StarRocksMVMonitor(host, int(port), user, password)
    if st.session_state.monitor.connect():
        st.sidebar.success("✅ Connected to StarRocks!")
    else:
        st.sidebar.error("❌ Failed to connect to StarRocks")

# Main title
st.title("📊 StarRocks Materialized View Monitor")

# Check if connected
if not hasattr(st.session_state.monitor, 'mv_monitor') or not st.session_state.monitor.mv_monitor.connection:
    st.warning("⚠️ Please connect to StarRocks first using the sidebar.")
    st.stop()

# Main content
tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "📋 Materialized Views", "🔄 Refresh History", "📊 Performance"])

with tab1:
    st.header("📈 Overview Dashboard")
    
    # Get statistics
    stats = st.session_state.monitor.get_mv_statistics()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Materialized Views", f"{stats['total_mvs']}")
    with col2:
        st.metric("Refresh Success Rate", f"{stats['refresh_success_rate']:.1f}%")
    with col3:
        avg_duration_str = f"{stats['avg_refresh_duration']:.2f}s" if stats['avg_refresh_duration'] > 0 else "N/A"
        st.metric("Avg. Refresh Duration", avg_duration_str)
    
    # Get materialized views data for overview
    mv_data = st.session_state.monitor.get_materialized_views()
    
    if not mv_data.empty:
        # Status distribution chart
        if 'last_refresh_state' in mv_data.columns:
            status_counts = mv_data['last_refresh_state'].value_counts()
            fig_status = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                title="Materialized Views Status Distribution",
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            st.plotly_chart(fig_status, use_container_width=True)
        
        # Show a few sample records
        st.subheader("Sample Materialized Views")
        st.dataframe(mv_data.head(10), use_container_width=True)

with tab2:
    st.header("📋 Materialized Views Detail")
    
    # Get materialized views data
    mv_data = st.session_state.monitor.get_materialized_views()
    
    if not mv_data.empty:
        # Filter by database if selected
        all_databases = mv_data['database_name'].unique().tolist()
        databases = ['All'] + sorted(all_databases)
        selected_db = st.selectbox("Filter by Database", databases)
        
        if selected_db != 'All':
            mv_data = mv_data[mv_data['database_name'] == selected_db]
        
        # Show materialized views table
        st.dataframe(mv_data, use_container_width=True)
        
        # Detailed view for a selected materialized view
        if not mv_data.empty:
            mv_names = mv_data['mv_name'].tolist()
            selected_mv = st.selectbox("Select Materialized View for Details", mv_names)
            
            if selected_mv:
                mv_details = mv_data[mv_data['mv_name'] == selected_mv].iloc[0]
                
                st.subheader(f"Details for {selected_mv}")
                details_df = pd.DataFrame({
                    'Property': mv_details.index,
                    'Value': mv_details.values
                })
                # Remove empty or null values for cleaner display
                details_df = details_df[details_df['Value'].notna() & (details_df['Value'] != '')]
                st.dataframe(details_df, use_container_width=True)
    else:
        st.info("No materialized views found.")

with tab3:
    st.header("🔄 Refresh History")
    
    # Select a materialized view to see its refresh history
    mv_data = st.session_state.monitor.get_materialized_views()
    
    if not mv_data.empty:
        mv_names = mv_data['mv_name'].tolist()
        mv_ids = mv_data['mv_id'].astype(str).tolist()
        
        # Create a mapping for selection
        mv_options = [f"{name} (ID: {id})" for name, id in zip(mv_names, mv_ids)]
        selected_option = st.selectbox("Select Materialized View", mv_options)
        
        # Extract mv_id from selection
        selected_mv_id = selected_option.split(" (ID: ")[1].rstrip(")")
        
        # Time range selection
        days = st.slider("Show history for last (days)", min_value=1, max_value=90, value=7)
        
        # Get refresh history
        task_name = f"mv-{selected_mv_id}"
        history_data = st.session_state.monitor.get_refresh_history(task_name=task_name, days=days)
        
        if not history_data.empty:
            st.subheader(f"Refresh History for MV ID: {selected_mv_id}")
            
            # Show history table
            st.dataframe(history_data, use_container_width=True)
            
            # Create visualization
            if 'start_time' in history_data.columns and 'state' in history_data.columns:
                # Status timeline chart
                fig_timeline = px.timeline(
                    history_data,
                    x_start='start_time',
                    x_end='end_time',
                    y='task_name',
                    color='state',
                    title="Refresh Time Timeline",
                    labels={'state': 'Status', 'start_time': 'Start Time', 'end_time': 'End Time'},
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_timeline.update_yaxes(showticklabels=False)
                st.plotly_chart(fig_timeline, use_container_width=True)
                
                # Status distribution chart
                if 'state' in history_data.columns:
                    status_counts = history_data['state'].value_counts()
                    fig_status = px.bar(
                        x=status_counts.index,
                        y=status_counts.values,
                        title="Refresh Status Distribution",
                        labels={'x': 'Status', 'y': 'Count'},
                        color=status_counts.index,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    st.plotly_chart(fig_status, use_container_width=True)
                
                # Duration chart if duration data is available
                if 'duration_seconds' in history_data.columns:
                    fig_duration = px.line(
                        history_data,
                        x='start_time',
                        y='duration_seconds',
                        title="Refresh Duration Over Time",
                        labels={'start_time': 'Time', 'duration_seconds': 'Duration (seconds)'}
                    )
                    st.plotly_chart(fig_duration, use_container_width=True)
        else:
            st.info(f"No refresh history found for materialized view ID: {selected_mv_id}")
    else:
        st.info("No materialized views found.")

with tab4:
    st.header("📊 Performance Metrics")
    
    # Time range selection for performance metrics
    perf_days = st.slider("Performance metrics for last (days)", min_value=1, max_value=90, value=30, key="perf_days")
    
    # Get performance metrics
    perf_metrics = st.session_state.monitor.get_refresh_performance_metrics(days=perf_days)
    
    if not perf_metrics.empty:
        st.subheader(f"Performance Metrics (Last {perf_days} Days)")
        st.dataframe(perf_metrics, use_container_width=True)
        
        # Visualize performance metrics
        if 'avg_duration' in perf_metrics.columns:
            fig_perf = px.bar(
                perf_metrics,
                x='task_name',
                y='avg_duration',
                title="Average Refresh Duration by Task",
                labels={'avg_duration': 'Duration (seconds)', 'task_name': 'Task Name'}
            )
            st.plotly_chart(fig_perf, use_container_width=True)
        
        if 'success_rate' in perf_metrics.columns:
            fig_success = px.bar(
                perf_metrics,
                x='task_name',
                y='success_rate',
                title="Success Rate by Task (%)",
                labels={'success_rate': 'Success Rate (%)', 'task_name': 'Task Name'}
            )
            st.plotly_chart(fig_success, use_container_width=True)
        
        # Get daily refresh status summary
        daily_summary = st.session_state.monitor.get_refresh_status_summary(days=perf_days)
        if not daily_summary.empty:
            st.subheader(f"Daily Refresh Status (Last {perf_days} Days)")
            
            fig_daily = px.line(
                daily_summary,
                x='date',
                y='count',
                color='state',
                title="Daily Refresh Count by Status",
                labels={'count': 'Number of Refreshes', 'date': 'Date', 'state': 'Status'}
            )
            st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.info(f"No performance metrics found for the last {perf_days} days.")

# Add footer
st.markdown("---")
st.markdown("*StarRocks Materialized View Monitor - Real-time monitoring and visualization of materialized view refresh status.*")