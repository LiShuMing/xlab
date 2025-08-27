import streamlit as st
import os

# Set page config
st.set_page_config(
    page_title="Finance AI Toolkit",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("📊 Finance AI Toolkit")
st.markdown("""
Welcome to the Finance AI Toolkit - a unified platform for financial analysis, 
blog content analysis, technical reporting, and database management.
""")

# Sidebar navigation
st.sidebar.title("Navigation")
app_mode = st.sidebar.selectbox(
    "Choose the tool you want to use:",
    [
        "Home",
        "Stock Analyzer Bot",
        "Blog Analyzer",
        "StarRocks SQL Generator",
        "ETF Momentum Analyzer"
    ]
)

# API Key Configuration
st.sidebar.title("API Configuration")
api_key = st.sidebar.text_input("DashScope API Key", type="password")

if api_key:
    os.environ["DASHSCOPE_API_KEY"] = api_key
    st.sidebar.success("API key configured!")

# Import and run selected app
if app_mode == "Home":
    st.markdown("""
    ## Available Tools
    
    1. **Stock Analyzer Bot** - Analyze stocks and make investment decisions with AI
    2. **Blog Analyzer** - Extract insights from technical blogs
    3. **StarRocks SQL Generator** - Generate SQL DDL and INSERT statements for StarRocks
    4. **ETF Momentum Analyzer** - Analyze ETF performance with momentum strategies
    
    Select a tool from the sidebar to get started!
    """)
    
    st.markdown("""
    ## How to Use
    
    1. Enter your DashScope API Key in the sidebar
    2. Select the tool you want to use from the navigation dropdown
    3. Follow the specific instructions for each tool
    
    ## Requirements
    
    - Python 3.7+
    - DashScope API key (get it from [DashScope Console](https://dashscope.console.aliyun.com/))
    """)
    
elif app_mode == "Stock Analyzer Bot":
    from apps.stock_analyzer import stock_analyzer_app
    stock_analyzer_app()
    
elif app_mode == "Blog Analyzer":
    from apps.blog_analyzer import blog_analyzer_app
    blog_analyzer_app()
    
elif app_mode == "StarRocks SQL Generator":
    from apps.starrocks_sql_generator import starrocks_sql_generator_app
    starrocks_sql_generator_app()
    
elif app_mode == "ETF Momentum Analyzer":
    from apps.etf_analyzer import etf_analyzer_app
    etf_analyzer_app()