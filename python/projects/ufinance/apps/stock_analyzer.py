import streamlit as st
import os
import yfinance as yf
import pandas as pd
import json
import re
from typing import Tuple

# Try to import DashScope
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    st.warning("DashScope not available. Some features may be limited.")


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


def call_qwen_api(prompt: str, language: str = "English") -> str:
    """Call Qwen API via DashScope or Anthropic API (OpenAI compatible)."""
    api_type, api_key, base_url = get_api_config()

    if not api_key:
        return "[API key not configured. Please set ANTHROPIC_API_KEY or DASHSCOPE_API_KEY.]"

    if api_type == "anthropic":
        return _call_anthropic_api(prompt, language, api_key, base_url)
    else:
        return _call_dashscope_api(prompt, language, api_key)


def _call_anthropic_api(prompt: str, language: str, api_key: str, base_url: str = None) -> str:
    """Call Anthropic API using the official Anthropic SDK."""
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
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


def _call_dashscope_api(prompt: str, language: str, api_key: str) -> str:
    """Call Qwen API via DashScope."""
    if not DASHSCOPE_AVAILABLE:
        return "[Qwen API not available. Please install dashscope package.]"

    try:
        dashscope.api_key = api_key
        response = Generation.call(
            model="qwen-max",
            messages=[
                {"role": "system", "content": f"You are a helpful assistant that responds in {language}."},
                {"role": "user", "content": prompt}
            ]
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return f"[API Error: {response.message}]"
    except Exception as e:
        return f"[Error calling Qwen API: {str(e)}]"

def get_stock_ticker(query: str) -> Tuple[str, str]:
    """Extract company name and ticker from query using Qwen"""
    prompt = f"""
    Given the user request, what is the company name and stock ticker?: {query}?
    Please respond in JSON format with keys "company_name" and "ticker_symbol".
    Example: {{"company_name": "Apple Inc.", "ticker_symbol": "AAPL"}}
    """

    response = call_qwen_api(prompt)

    # Try to extract JSON from response
    try:
        # Find JSON in response
        start = response.find('{')
        end = response.rfind('}') + 1
        if start != -1 and end != 0:
            json_str = response[start:end]
            data = json.loads(json_str)
            return data.get("company_name", ""), data.get("ticker_symbol", "")
    except:
        pass

    # Fallback regex extraction
    company_match = re.search(r'"company_name":\s*"([^"]+)"', response)
    ticker_match = re.search(r'"ticker_symbol":\s*"([^"]+)"', response)

    company_name = company_match.group(1) if company_match else ""
    ticker_symbol = ticker_match.group(1) if ticker_match else ""

    return company_name, ticker_symbol

def get_stock_price(ticker: str, history: int = 30) -> str:
    """Get stock price data"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{history}d")
        if not hist.empty:
            return hist.to_string()
        else:
            return "No data available"
    except Exception as e:
        return f"Error fetching stock data: {str(e)}"

def get_financial_statements(ticker: str) -> str:
    """Get financial statements"""
    try:
        company = yf.Ticker(ticker)
        balance_sheet = company.balance_sheet
        if balance_sheet.shape[1] >= 3:
            balance_sheet = balance_sheet.iloc[:,:3]
        balance_sheet = balance_sheet.dropna(how="any")
        return balance_sheet.to_string() if not balance_sheet.empty else "No financial data available"
    except Exception as e:
        return f"Error fetching financial data: {str(e)}"

def get_recent_stock_news(company_name: str) -> str:
    """Get recent stock news (placeholder)"""
    return f"Recent news for {company_name} would be displayed here in a full implementation."

def analyze_stock(query: str, language: str = "English") -> str:
    """Analyze stock using Qwen API"""
    try:
        company_name, ticker = get_stock_ticker(query)
        
        if not company_name or not ticker:
            return "Could not extract company name and ticker from the query."
        
        # Get stock data
        stock_data = get_stock_price(ticker, history=30)
        stock_financials = get_financial_statements(ticker)
        stock_news = get_recent_stock_news(company_name)
        
        available_information = f"""
        Company: {company_name} ({ticker})
        Stock Price Data: {stock_data}
        Financial Statements: {stock_financials}
        Recent News: {stock_news}
        """
        
        # Get analysis from Qwen
        prompt = f"""
        You are a senior stock analyst working for a financial advisory firm. 
        Give detailed stock analysis. Use the available data and provide investment recommendation.
        The user is fully aware about investment risks, don't include any warnings about consulting advisors.
        
        User question: {query}
        You have the following information about {company_name}. 
        Write 5-8 pointwise investment analysis to answer user query.
        Conclude with proper explanation. Include both positives and negatives:
        {available_information}
        """
        
        analysis = call_qwen_api(prompt, language)
        return analysis
    except Exception as e:
        return f"Error in stock analysis: {str(e)}"

def stock_analyzer_app():
    """Main function for the Stock Analyzer app"""
    st.title("📈 Stock Analyzer Bot")
    st.markdown("Analyze stocks and get investment recommendations with AI assistance.")
    
    # Input query
    query = st.text_input("Enter your investment related query:", 
                         placeholder="e.g., Is it a good time to invest in Apple?")
    
    # Language selection
    language = st.selectbox("Output Language", ["English", "Chinese"])
    
    # Analyze button
    if st.button("Analyze Stock", type="primary"):
        if not query:
            st.warning("Please enter a query")
            return
            
        if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("DASHSCOPE_API_KEY"):
            st.error("Please configure your API Key in the sidebar (Anthropic or DashScope).")
            return
        
        try:
            with st.spinner("Analyzing stock..."):
                # Get analysis
                analysis_result = analyze_stock(query, language)

                # Display results
                st.success("Analysis completed!")
                st.markdown(analysis_result)

        except Exception as e:
            st.error(f"Error analyzing stock: {str(e)}")
    
    # Example usage
    with st.expander("How to use"):
        st.markdown("""
        1. Enter your investment-related query (e.g., "Is it a good time to invest in Tesla?")
        2. Select the output language
        3. Click "Analyze Stock" to get AI-powered investment recommendations
        """)

if __name__ == "__main__":
    stock_analyzer_app()