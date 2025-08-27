import streamlit as st
import requests
from bs4 import BeautifulSoup
import html2text
import os

# Try to import DashScope
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    st.warning("DashScope not available. Some features may be limited.")

def call_qwen_api(prompt: str, language: str = "English") -> str:
    """Call Qwen API via DashScope"""
    if not DASHSCOPE_AVAILABLE:
        return "[Qwen API not available. Please install dashscope package.]"
    
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        return "[API key not configured. Please set DASHSCOPE_API_KEY.]"
    
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

def fetch_blog_content(url: str) -> str:
    """Fetch and convert blog content to markdown"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Convert to markdown
        h = html2text.HTML2Text()
        h.ignore_links = False
        markdown_content = h.handle(str(soup))
        
        return markdown_content
    except Exception as e:
        raise Exception(f"Error fetching blog content: {str(e)}")

def analyze_blog_content(content: str, analysis_options: list, language: str = "English") -> str:
    """Analyze blog content and extract insights"""
    
    # Truncate content if too long
    truncated_content = content[:3000] + "..." if len(content) > 3000 else content
    
    results = []
    
    # Add title
    title = extract_title(content)
    results.append(f"# {title} Analysis\n")
    
    # Summary analysis
    if "Summary" in analysis_options:
        summary = generate_summary(truncated_content, language)
        results.append(f"## Summary\n{summary}\n")
    
    # Technical insights
    if "Technical Insights" in analysis_options:
        insights = extract_technical_insights(truncated_content, language)
        results.append(f"## Technical Insights\n{insights}\n")
    
    # Language notes
    if "Language Notes" in analysis_options:
        language_notes = extract_language_notes(truncated_content, language)
        results.append(f"## Language Notes\n{language_notes}\n")
    
    return "\n".join(results)

def extract_title(content: str) -> str:
    """Extract title from content"""
    lines = content.split('\n')
    for line in lines:
        if line.startswith('# '):
            return line[2:].strip()
    return "Blog Post"

def generate_summary(content: str, language: str) -> str:
    """Generate a summary of the blog content"""
    prompt = f"""
    Please provide a concise summary of the following technical blog post in {language}.
    The summary should be 3-5 paragraphs long and capture the key ideas and main points.
    
    Blog Content:
    {content}
    
    Summary:
    """
    
    return call_qwen_api(prompt, language)

def extract_technical_insights(content: str, language: str) -> str:
    """Extract technical insights and explain key terms"""
    prompt = f"""
    As a senior engineer, analyze the following technical blog post and explain core concepts and terms.
    For each important technical term, provide:
    - The term name
    - A detailed explanation from a senior engineer's perspective
    - Practical implications or use cases
    
    Format the output as a markdown list with each term as a bullet point.
    
    Please provide the response in {language}.
    
    Blog Content:
    {content}
    
    Technical Insights:
    """
    
    return call_qwen_api(prompt, language)

def extract_language_notes(content: str, language: str) -> str:
    """Extract language learning notes including key terms and cultural references"""
    prompt = f"""
    As an English language expert, analyze the following technical blog post and extract language learning materials.
    
    Please identify:
    1. 20-50 key English terms and phrases with their translations
    2. Cultural references like allusions and idioms with explanations
    
    Format the output as a markdown list with clear sections for:
    - Key Terms and Phrases
    - Cultural References
    
    Please provide the response in {language}.
    
    Blog Content:
    {content}
    
    Language Notes:
    """
    
    return call_qwen_api(prompt, language)

def blog_analyzer_app():
    """Main function for the Blog Analyzer app"""
    st.title("📝 Blog Analyzer")
    st.markdown("Analyze English technical blogs and extract key insights, technical concepts, and language learning notes.")
    
    # Input URL
    url = st.text_input("Enter blog URL:", placeholder="https://example.com/blog-post")
    
    # Analysis options
    analysis_options = st.multiselect(
        "Select analysis options:",
        ["Summary", "Technical Insights", "Language Notes"],
        ["Summary", "Technical Insights", "Language Notes"]
    )
    
    # Language selection
    language = st.selectbox("Output Language", ["English", "Chinese"])
    
    # Analyze button
    if st.button("Analyze Blog", type="primary"):
        if not url:
            st.warning("Please enter a valid URL")
            return
            
        if not os.getenv("DASHSCOPE_API_KEY"):
            st.error("Please configure your DashScope API Key in the sidebar.")
            return
        
        try:
            with st.spinner("Fetching and analyzing blog content..."):
                # Fetch blog content
                content = fetch_blog_content(url)
                
                # Analyze content
                analysis_result = analyze_blog_content(content, analysis_options, language)
                
                # Display results
                st.success("Analysis completed!")
                st.markdown(analysis_result)
                
        except Exception as e:
            st.error(f"Error analyzing blog: {str(e)}")
    
    # Example usage
    with st.expander("How to use"):
        st.markdown("""
        1. Enter the URL of an English technical blog
        2. Select the type of analysis you want
        3. Click "Analyze Blog" to get insights
        4. Learn key technical concepts and improve your English
        """)

if __name__ == "__main__":
    blog_analyzer_app()