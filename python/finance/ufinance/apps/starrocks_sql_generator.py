import streamlit as st
import json
import os

# Try importing DashScope SDK
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    st.warning("DashScope SDK not found. Please install it to use the AI features.")

def generate_sql_with_qwen(user_query: str, api_key: str) -> dict:
    """
    Generate StarRocks DDL and INSERT statements using Qwen AI via DashScope.
    
    Args:
        user_query (str): The SQL query provided by the user
        api_key (str): DashScope API key for authentication
        
    Returns:
        dict: Parsed response with DDLs and INSERT statements
    """
    if not DASHSCOPE_AVAILABLE:
        return {
            "ddls": ["-- DashScope SDK not available"],
            "inserts": ["-- DashScope SDK not available"]
        }
        
    try:
        # Configure DashScope with API key
        dashscope.api_key = api_key
        
        # System prompt for Qwen
        system_prompt = f"""You are a StarRocks SQL expert. Given a SQL query: {user_query}, generate:
1. CREATE TABLE DDL for all dependent tables, strictly following StarRocks syntax.
2. INSERT INTO statements with sample data for each table.

Rules:
- Do not use DEFAULT values for columns.
- Avoid specifying PRIMARY KEY unless necessary.
- For partitions, use double quotes for values (e.g., PARTITION BY RANGE (date) (PARTITION p1 VALUES LESS THAN ("2023-01-01"))).
- Infer reasonable column names and types from the query (e.g., if 'age > 18', make age INT).
- Ensure DDL is valid StarRocks syntax: e.g., CREATE TABLE tbl (col1 INT, col2 VARCHAR(255)) ENGINE=OLAP DISTRIBUTED BY HASH(col1) BUCKETS 10 PROPERTIES("replication_num"="1");
- If query is partial, assume minimal tables/columns needed.
- Output in JSON format: {{"ddls": ["CREATE TABLE ..."], "inserts": ["INSERT INTO ... VALUES ..."]}}"""

        # Call Qwen model via DashScope
        response = Generation.call(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.3,
            result_format="message"
        )
        
        # Check if the response is successful
        if response.status_code != 200:
            raise Exception(f"DashScope API error: {response.message}")
        
        # Parse the response
        try:
            # Extract content from the response
            content = response.output.choices[0].message.content
            
            # Try to parse as JSON directly
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            # If not JSON, try to extract JSON from the response
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != 0:
                json_str = content[start:end]
                result = json.loads(json_str)
                return result
            else:
                # If we still can't parse JSON, return the raw content
                return {
                    "ddls": [f"-- Could not parse JSON. Raw response: {content[:200]}..."],
                    "inserts": [f"-- Could not parse JSON. Raw response: {content[:200]}..."]
                }
                
    except Exception as e:
        st.error(f"Error generating SQL: {str(e)}")
        return {
            "ddls": [f"-- Error generating DDL: {str(e)}"],
            "inserts": [f"-- Error generating INSERT: {str(e)}"]
        }

def starrocks_sql_generator_app():
    """Main function for the StarRocks SQL Generator app"""
    st.set_page_config(page_title="StarRocks SQL Generator AI Agent", page_icon="🤖")
    
    st.title("StarRocks SQL Generator AI Agent")
    st.markdown("""
    This tool generates StarRocks-compatible CREATE TABLE DDL and INSERT statements 
    based on your SQL query using Qwen AI via DashScope.
    """)
    
    # Display SDK status
    if DASHSCOPE_AVAILABLE:
        st.success("DashScope SDK is available")
    else:
        st.error("DashScope SDK is not available. Please install it with: pip install dashscope")
    
    # Get API key from environment variable
    api_key = None
    if "DASHSCOPE_API_KEY" in os.environ:
        api_key = os.environ["DASHSCOPE_API_KEY"]
        st.info("Using DASHSCOPE_API_KEY from environment variable")
    else:
        api_key = st.text_input("Enter your DashScope API Key:", type="password")
        st.warning("API key not found in environment. Please enter it above.")
    
    # SQL query input
    user_query = st.text_area(
        "Enter your SQL query:",
        placeholder="SELECT name, age FROM users WHERE age > 18",
        height=150
    )
    
    # Generate button
    if st.button("Generate DDL and Insert SQL", type="primary"):
        if not user_query.strip():
            st.warning("Please enter a SQL query.")
            return
            
        if not api_key:
            st.error("Please provide a DashScope API Key.")
            return
        
        with st.spinner("Generating SQL statements..."):
            # Generate SQL using Qwen via DashScope
            result = generate_sql_with_qwen(user_query, api_key)
            
            # Display results
            if "ddls" in result and "inserts" in result:
                st.subheader("Generated CREATE TABLE Statements")
                for i, ddl in enumerate(result["ddls"]):
                    st.code(ddl, language="sql")
                
                st.subheader("Generated INSERT Statements")
                for i, insert in enumerate(result["inserts"]):
                    st.code(insert, language="sql")
                    
                # Option to download the results
                result_json = json.dumps(result, indent=2)
                st.download_button(
                    label="Download Results",
                    data=result_json,
                    file_name="starrocks_sql_result.json",
                    mime="application/json"
                )
            else:
                st.error("Invalid response format from Qwen. Please try again.")
    else:
        st.info("Enter your SQL query and click 'Generate DDL and Insert SQL' to get started.")
        
    # Additional information
    with st.expander("How to use this tool"):
        st.markdown("""
        1. Enter your SQL query in the text area above
        2. Click the "Generate DDL and Insert SQL" button
        3. View the generated CREATE TABLE and INSERT statements
        4. Download the results as JSON if needed
        
        **Tips:**
        - The tool works with both complete and partial SQL queries
        - For complex queries, multiple tables may be generated
        - Generated statements follow StarRocks syntax
        """)
        
    # StarRocks syntax reference
    with st.expander("StarRocks Syntax Reference"):
        st.markdown("""
        **Basic CREATE TABLE:**
        ```sql
        CREATE TABLE table_name (
            column_name data_type [NULL | NOT NULL] [COMMENT 'comment'],
            ...
        ) 
        [ENGINE = [olap|mysql|elasticsearch|hive|iceberg|jdbc|hudi]] 
        [key_desc] 
        [partition_desc] 
        [distribution_desc] 
        [rollup_index] 
        [PROPERTIES ("key"="value", ...)] 
        [COMMENT "table_comment"];
        ```
        
        **Common ENGINE:** OLAP
        
        **Distribution:**
        ```sql
        DISTRIBUTED BY HASH(column_list) BUCKETS bucket_number
        ```
        """)

if __name__ == "__main__":
    starrocks_sql_generator_app()