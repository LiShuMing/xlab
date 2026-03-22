"""
Blog Analyzer module - Extract insights from technical blogs.

Features:
- Web scraping to extract blog content
- Summary generation
- Technical insights extraction
- Language learning notes
"""

import re
from typing import List
import streamlit as st
import requests
from bs4 import BeautifulSoup
import html2text

from modules.base_module import BaseModule, register_module
from core.llm_factory import get_llm, get_available_providers


@register_module
class BlogAnalyzerModule(BaseModule):
    """
    Blog Analyzer module for extracting insights from technical blogs.
    
    Features:
    - Fetches and parses blog content from URLs
    - Generates concise summaries
    - Extracts technical concepts and explanations
    - Provides language learning notes
    - Multi-language output support
    """
    
    name = "Blog Analyzer"
    description = "Extract insights from technical blogs with AI analysis"
    icon = "📝"
    order = 30
    
    # Analysis options
    ANALYSIS_OPTIONS = ["Summary", "Technical Insights", "Language Notes"]
    
    def render(self) -> None:
        """Render the blog analyzer interface."""
        self.display_header()
        
        # URL input
        url = st.text_input(
            "Enter blog URL:",
            placeholder="https://example.com/technical-blog-post"
        )
        
        # Analysis options
        analysis_options = st.multiselect(
            "Select analysis options:",
            options=self.ANALYSIS_OPTIONS,
            default=["Summary", "Technical Insights"]
        )
        
        # Language selection
        language = st.selectbox("Output Language", ["English", "Chinese"])
        
        # Model settings
        with st.expander("⚙️ Model Settings"):
            col1, col2 = st.columns(2)
            with col1:
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.7,
                    step=0.1,
                    key="blog_temp"
                )
            with col2:
                max_tokens = st.slider(
                    "Max Tokens",
                    min_value=500,
                    max_value=4000,
                    value=2000,
                    step=100,
                    key="blog_tokens"
                )
        
        # Analyze button
        if st.button("Analyze Blog", type="primary", use_container_width=True):
            if not url:
                st.warning("Please enter a valid URL")
                return
            
            if not analysis_options:
                st.warning("Please select at least one analysis option")
                return
            
            # Check API configuration
            if not get_available_providers():
                st.error("Please configure at least one API key (DashScope, OpenAI, or Anthropic).")
                return
            
            try:
                with st.spinner("🌐 Fetching blog content..."):
                    content = self._fetch_blog_content(url)
                    
                with st.spinner("🤖 Analyzing content..."):
                    analysis_result = self._analyze_content(
                        content, analysis_options, language, temperature, max_tokens
                    )
                    
                st.success("✅ Analysis completed!")
                st.markdown(analysis_result)
                
            except Exception as e:
                st.error(f"Error analyzing blog: {str(e)}")
        
        # How to use
        with st.expander("ℹ️ How to use"):
            st.markdown("""
            1. **Enter blog URL** - Paste the URL of an English technical blog
            2. **Select analysis** - Choose what insights you want:
               - **Summary** - Concise overview of the article
               - **Technical Insights** - Key concepts explained by an expert
               - **Language Notes** - Vocabulary and cultural references
            3. **Choose language** - Output in English or Chinese
            4. **Click Analyze** - Get AI-powered blog analysis
            
            **Tips:**
            - Works best with technical blogs and articles
            - Some sites may block scraping (HTTP 451 error)
            - For long articles, content is automatically truncated
            """)
    
    def _fetch_blog_content(self, url: str) -> str:
        """
        Fetch and convert blog content to markdown.
        
        Args:
            url: Blog URL
        
        Returns:
            Blog content as markdown string
        
        Raises:
            Exception: If fetching fails or site blocks access
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, timeout=15, headers=headers)
            response.raise_for_status()
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            markdown_content = h.handle(str(soup))
            
            return markdown_content
            
        except requests.HTTPError as e:
            if "451" in str(e):
                raise Exception(
                    "Site blocked access (HTTP 451). This website doesn't allow automated access. "
                    "Try a different blog URL."
                )
            raise Exception(f"Failed to fetch blog: {str(e)}")
        except Exception as e:
            raise Exception(f"Error fetching blog content: {str(e)}")
    
    def _analyze_content(
        self,
        content: str,
        analysis_options: List[str],
        language: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """
        Analyze blog content based on selected options.
        
        Args:
            content: Blog content as markdown
            analysis_options: Selected analysis types
            language: Output language
            temperature: LLM temperature
            max_tokens: Max tokens for response
        
        Returns:
            Analysis result as markdown string
        """
        # Truncate content if too long
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n[Content truncated due to length...]"
        
        # Extract title
        title = self._extract_title(content)
        
        # Build results
        results = [f"# {title}\n"]
        
        # Get LLM for analysis
        llm = get_llm(
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=False
        )
        
        # Generate summary
        if "Summary" in analysis_options:
            with st.spinner("📝 Generating summary..."):
                summary = self._generate_summary(llm, content, language)
                results.append(f"## 📋 Summary\n{summary}\n")
        
        # Extract technical insights
        if "Technical Insights" in analysis_options:
            with st.spinner("💡 Extracting technical insights..."):
                insights = self._extract_technical_insights(llm, content, language)
                results.append(f"## 🔧 Technical Insights\n{insights}\n")
        
        # Extract language notes
        if "Language Notes" in analysis_options:
            with st.spinner("📚 Analyzing language..."):
                language_notes = self._extract_language_notes(llm, content, language)
                results.append(f"## 🌍 Language Notes\n{language_notes}\n")
        
        return "\n".join(results)
    
    def _extract_title(self, content: str) -> str:
        """Extract title from markdown content."""
        lines = content.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        return "Blog Analysis"
    
    def _generate_summary(self, llm, content: str, language: str) -> str:
        """Generate summary of blog content."""
        prompt = f"""Please provide a concise summary of the following technical blog post in {language}.
The summary should be 3-5 paragraphs long and capture the key ideas and main points.

Blog Content:
{content}

Summary:"""
        
        response = llm.invoke(prompt)
        return response.content
    
    def _extract_technical_insights(self, llm, content: str, language: str) -> str:
        """Extract technical insights and explain key terms."""
        prompt = f"""As a senior engineer, analyze the following technical blog post and explain core concepts and terms.
For each important technical term, provide:
- The term name
- A detailed explanation from a senior engineer's perspective
- Practical implications or use cases

Format the output as a markdown list with each term as a bullet point.

Please provide the response in {language}.

Blog Content:
{content}

Technical Insights:"""
        
        response = llm.invoke(prompt)
        return response.content
    
    def _extract_language_notes(self, llm, content: str, language: str) -> str:
        """Extract language learning notes."""
        prompt = f"""As an English language expert, analyze the following technical blog post and extract language learning materials.

Please identify:
1. 20-50 key English terms and phrases with their translations
2. Cultural references like allusions and idioms with explanations

Format the output as a markdown list with clear sections for:
- Key Terms and Phrases
- Cultural References

Please provide the response in {language}.

Blog Content:
{content}

Language Notes:"""
        
        response = llm.invoke(prompt)
        return response.content
