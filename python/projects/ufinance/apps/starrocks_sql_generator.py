import streamlit as st
import json
import os


def get_api_config():
    """Get API configuration from environment variables.

    Returns:
        tuple: (api_type, api_key, base_url)
        - api_type: "anthropic" or "dashscope"
        - api_key: the API key to use
        - base_url: the base URL for API calls (None for DashScope)
    """
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    anthropic_base_url = os.getenv("ANTHROPIC_BASE_URL")

    if anthropic_api_key:
        return "anthropic", anthropic_api_key, anthropic_base_url

    # Fall back to DashScope
    dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
    return "dashscope", dashscope_api_key, None


def _call_anthropic_api(system_prompt: str, user_query: str, api_key: str, base_url: str = None) -> str:
    """Call Anthropic API using the official Anthropic SDK."""
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_query}
            ],
        )

        # Handle response content (may include thinking blocks)
        text_content = []
        for block in response.content:
            if hasattr(block, 'text'):
                text_content.append(block.text)
            elif hasattr(block, 'type') and block.type == 'text':
                text_content.append(str(block))
        return ''.join(text_content)
    except ImportError:
        return "[Anthropic SDK not available. Please install anthropic package.]"
    except Exception as e:
        return f"[Anthropic API Error: {str(e)}]"


def _call_dashscope_api(system_prompt: str, user_query: str, api_key: str) -> str:
    """Call Qwen API via DashScope."""
    try:
        import dashscope
        from dashscope import Generation

        dashscope.api_key = api_key

        response = Generation.call(
            model="qwen-max",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=0.3,
            result_format="message"
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return f"[DashScope API Error: {response.message}]"
    except ImportError:
        return "[DashScope SDK not available. Please install dashscope package.]"
    except Exception as e:
        return f"[Error calling Qwen API: {str(e)}]"


def generate_sql_with_qwen(user_query: str) -> dict:
    """
    Generate StarRocks DDL and INSERT statements using Qwen AI via DashScope or Anthropic API.

    Args:
        user_query (str): The SQL query provided by the user

    Returns:
        dict: Parsed response with DDLs and INSERT statements
    """
    api_type, api_key, base_url = get_api_config()

    if not api_key:
        return {
            "ddls": ["-- API key not configured. Set ANTHROPIC_API_KEY or DASHSCOPE_API_KEY."],
            "inserts": ["-- API key not configured. Set ANTHROPIC_API_KEY or DASHSCOPE_API_KEY."]
        }

    # System prompt for the AI
    system_prompt = """You are a StarRocks SQL expert. Given a SQL query, generate:
1. CREATE TABLE DDL for all dependent tables, strictly following StarRocks syntax.
2. INSERT INTO statements with sample data for each table.

Rules:
- Do not use DEFAULT values for columns.
- Avoid specifying PRIMARY KEY unless necessary.
- For partitions, use double quotes for values (e.g., PARTITION BY RANGE (date) (PARTITION p1 VALUES LESS THAN ("2023-01-01"))).
- Infer reasonable column names and types from the query (e.g., if 'age > 18', make age INT).
- Ensure DDL is valid StarRocks syntax: e.g., CREATE TABLE tbl (col1 INT, col2 VARCHAR(255)) ENGINE=OLAP DISTRIBUTED BY HASH(col1) BUCKETS 10 PROPERTIES("replication_num"="1");
- If query is partial, assume minimal tables/columns needed.
- Output in JSON format: {"ddls": ["CREATE TABLE ..."], "inserts": ["INSERT INTO ... VALUES ..."]}"""

    try:
        if api_type == "anthropic":
            content = _call_anthropic_api(system_prompt, user_query, api_key, base_url)
        else:
            content = _call_dashscope_api(system_prompt, user_query, api_key)

        # Check for API errors
        if content.startswith("[") and content.endswith("]"):
            raise Exception(content)

        # Parse the response as JSON
        try:
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
    based on your SQL query using Qwen AI via DashScope or Anthropic API.
    """)

    # Display current API provider
    api_type, _, _ = get_api_config()
    if api_type == "anthropic":
        st.info("Using Anthropic API")
    elif api_type == "dashscope":
        st.info("Using DashScope API")
    else:
        st.warning("No API key configured. Set ANTHROPIC_API_KEY or DASHSCOPE_API_KEY.")

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("DASHSCOPE_API_KEY"):
        st.error("Please configure your API Key in the sidebar (Anthropic or DashScope).")
        return

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

        with st.spinner("Generating SQL statements..."):
            # Generate SQL using Qwen via DashScope or Anthropic
            result = generate_sql_with_qwen(user_query)
            
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