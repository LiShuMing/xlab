"""
StarRocks SQL Generator module - Generate DDL and INSERT statements.

Features:
- Generate StarRocks-compatible CREATE TABLE DDL
- Generate sample INSERT statements
- Support complex SQL queries
- JSON export functionality
"""

import json
import re
from typing import Dict, List
import streamlit as st

from modules.base_module import BaseModule, register_module
from core.llm_factory import get_llm, get_available_providers


@register_module
class StarRocksSQLModule(BaseModule):
    """
    StarRocks SQL Generator module.
    
    Generates StarRocks-compatible CREATE TABLE DDL and INSERT statements
    based on user SQL queries using AI.
    """
    
    name = "StarRocks SQL"
    description = "Generate StarRocks DDL and INSERT statements from SQL queries"
    icon = "🗄️"
    order = 40
    
    # System prompt for SQL generation
    SYSTEM_PROMPT = """You are a StarRocks SQL expert. Given a SQL query, generate:
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
    
    def render(self) -> None:
        """Render the StarRocks SQL generator interface."""
        self.display_header()
        
        # API status
        available_providers = get_available_providers()
        if not available_providers:
            st.error("⚠️ No API keys configured. Please set ANTHROPIC_API_KEY, DASHSCOPE_API_KEY, or OPENAI_API_KEY.")
            return
        
        st.info(f"✅ Using: {', '.join(available_providers)}")
        
        # Model settings
        col1, col2 = st.columns(2)
        with col1:
            temperature = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=0.3,
                step=0.1,
                key="sql_temp",
                help="Lower temperature for more consistent SQL generation"
            )
        with col2:
            max_tokens = st.slider(
                "Max Tokens",
                min_value=1000,
                max_value=4000,
                value=3000,
                step=100,
                key="sql_tokens"
            )
        
        # SQL query input
        user_query = st.text_area(
            "Enter your SQL query:",
            placeholder="SELECT name, age FROM users WHERE age > 18",
            height=150,
            help="Enter a SQL query to generate corresponding DDL and INSERT statements"
        )
        
        # Generate button
        if st.button("Generate DDL and INSERT SQL", type="primary", use_container_width=True):
            if not user_query.strip():
                st.warning("Please enter a SQL query.")
                return
            
            try:
                with st.spinner("🤖 Generating SQL statements..."):
                    result = self._generate_sql(user_query, temperature, max_tokens)
                
                # Display results
                self._display_results(result)
                
            except Exception as e:
                st.error(f"Error generating SQL: {str(e)}")
        
        # Reference sections
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("ℹ️ How to use"):
                st.markdown("""
                1. **Enter SQL query** - Write a SELECT query referencing tables you need
                2. **Click Generate** - AI will create DDL and INSERT statements
                3. **Review results** - Check generated SQL for correctness
                4. **Download** - Export results as JSON if needed
                
                **Tips:**
                - Works with both complete and partial SQL queries
                - For complex queries, multiple tables may be generated
                - Generated statements follow StarRocks syntax
                """)
        
        with col2:
            with st.expander("📚 StarRocks Syntax Reference"):
                st.markdown("""
                **Basic CREATE TABLE:**
                ```sql
                CREATE TABLE table_name (
                    col1 INT,
                    col2 VARCHAR(255),
                    ...
                )
                ENGINE = OLAP
                DISTRIBUTED BY HASH(col1) BUCKETS 10
                PROPERTIES ("replication_num"="1");
                ```
                
                **Key Features:**
                - ENGINE: OLAP (default), MySQL, Hive, etc.
                - DISTRIBUTED BY HASH: Data distribution
                - PARTITION BY RANGE: Time-based partitioning
                """)
    
    def _generate_sql(self, user_query: str, temperature: float, max_tokens: int) -> Dict:
        """
        Generate SQL DDL and INSERT statements.
        
        Args:
            user_query: User's SQL query
            temperature: LLM temperature
            max_tokens: Max tokens for response
        
        Returns:
            Dictionary with 'ddls' and 'inserts' keys
        """
        llm = get_llm(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=False
        )
        
        # Prepare messages with system prompt
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=user_query)
        ]
        
        # Get response
        response = llm.invoke(messages)
        content = response.content
        
        # Parse JSON response
        return self._parse_response(content)
    
    def _parse_response(self, content: str) -> Dict:
        """
        Parse LLM response to extract JSON.
        
        Args:
            content: Raw LLM response
        
        Returns:
            Parsed dictionary with ddls and inserts
        """
        try:
            # Try direct JSON parsing
            result = json.loads(content)
            if "ddls" in result and "inserts" in result:
                return result
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        code_block_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
        matches = re.findall(code_block_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                result = json.loads(match.strip())
                if "ddls" in result and "inserts" in result:
                    return result
            except json.JSONDecodeError:
                continue
        
        # Try to find JSON object in response
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            try:
                json_str = content[start:end]
                result = json.loads(json_str)
                if "ddls" in result and "inserts" in result:
                    return result
            except json.JSONDecodeError:
                pass
        
        # Return error if parsing failed
        return {
            "ddls": [f"-- Could not parse response. Raw output:\n{content[:500]}..."],
            "inserts": ["-- Parsing error"]
        }
    
    def _display_results(self, result: Dict) -> None:
        """
        Display SQL generation results.
        
        Args:
            result: Dictionary with ddls and inserts
        """
        if "ddls" in result and result["ddls"]:
            st.subheader("📋 Generated CREATE TABLE Statements")
            for i, ddl in enumerate(result["ddls"], 1):
                st.code(ddl, language="sql")
        
        if "inserts" in result and result["inserts"]:
            st.subheader("📝 Generated INSERT Statements")
            for i, insert in enumerate(result["inserts"], 1):
                st.code(insert, language="sql")
        
        # Download option
        result_json = json.dumps(result, indent=2)
        st.download_button(
            label="📥 Download Results (JSON)",
            data=result_json,
            file_name="starrocks_sql_result.json",
            mime="application/json",
            use_container_width=True
        )
