"""
Concrete renderer implementations for report output.

Supports Markdown, HTML, and JSON formats.
"""

import json
from typing import Any, Dict
from datetime import datetime

from utils.output.base import BaseRenderer, Report, ReportFormat, ReportSection


class MarkdownRenderer(BaseRenderer):
    """
    Renderer for Markdown format.
    
    Default format that preserves LLM output with minimal processing.
    """
    
    format = ReportFormat.MARKDOWN
    
    def render(self, report: Report) -> str:
        """
        Render report as Markdown.
        
        If report has raw content, use it directly.
        Otherwise, build from structured sections.
        """
        if report.content:
            return report.content
        
        # Build from sections
        lines = [
            f"# {report.metadata.title}",
            "",
            f"**Company:** {report.company_name} ({report.ticker})",
            f"**Date:** {report.metadata.created_at}",
            f"**Author:** {report.metadata.author}",
            "",
            "---",
            "",
        ]
        
        # Add sections in order
        section_order = [
            ReportSection.OVERVIEW,
            ReportSection.MACRO,
            ReportSection.TECHNICAL,
            ReportSection.FUNDAMENTAL,
            ReportSection.MULTI_LENS,
            ReportSection.RISK,
            ReportSection.POSITION,
            ReportSection.RATING,
        ]
        
        for section in section_order:
            content = report.sections.get(section)
            if content:
                lines.extend([content, "", "---", ""])
        
        return "\n".join(lines)
    
    def get_content_type(self) -> str:
        """Get MIME type for Markdown."""
        return "text/markdown"


class HtmlRenderer(BaseRenderer):
    """
    Renderer for HTML format with styling.
    
    Converts Markdown content to HTML with CSS styling.
    """
    
    format = ReportFormat.HTML
    
    # Enhanced CSS with beautiful fonts and color hierarchy
    DEFAULT_CSS = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
        
        :root {
            /* Primary Colors - Elegant Blue-Purple Gradient Base */
            --primary-50: #eef2ff;
            --primary-100: #e0e7ff;
            --primary-200: #c7d2fe;
            --primary-300: #a5b4fc;
            --primary-400: #818cf8;
            --primary-500: #6366f1;
            --primary-600: #4f46e5;
            --primary-700: #4338ca;
            --primary-800: #3730a3;
            --primary-900: #312e81;
            
            /* Semantic Colors */
            --bg-color: #fafbfc;
            --bg-secondary: #ffffff;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-tertiary: #94a3b8;
            --border-color: #e2e8f0;
            --border-light: #f1f5f9;
            
            /* Accent Gradient */
            --accent-start: #4f46e5;
            --accent-end: #7c3aed;
            --accent-color: var(--primary-600);
            
            /* Section Backgrounds with subtle colors */
            --section-bg: #ffffff;
            --highlight-bg: #f8fafc;
            --code-bg: #f1f5f9;
            
            /* Status Colors with better harmony */
            --success-color: #10b981;
            --success-bg: #d1fae5;
            --warning-color: #f59e0b;
            --warning-bg: #fef3c7;
            --danger-color: #ef4444;
            --danger-bg: #fee2e2;
            --info-color: #3b82f6;
            --info-bg: #dbeafe;
            
            /* Shadows */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            
            /* Border Radius */
            --radius-sm: 6px;
            --radius: 10px;
            --radius-lg: 16px;
            --radius-xl: 24px;
        }
        
        @media (prefers-color-scheme: dark) {
            :root {
                --bg-color: #0f172a;
                --bg-secondary: #1e293b;
                --text-primary: #f8fafc;
                --text-secondary: #cbd5e1;
                --text-tertiary: #94a3b8;
                --border-color: #334155;
                --border-light: #1e293b;
                --section-bg: #1e293b;
                --highlight-bg: #334155;
                --code-bg: #0f172a;
            }
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            font-weight: 400;
            line-height: 1.7;
            color: var(--text-primary);
            background: linear-gradient(135deg, var(--bg-color) 0%, var(--primary-50) 100%);
            min-height: 100vh;
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 24px;
        }
        
        /* Header Section with Gradient */
        .report-header {
            background: linear-gradient(135deg, var(--accent-start) 0%, var(--accent-end) 100%);
            border-radius: var(--radius-lg);
            padding: 40px;
            margin-bottom: 40px;
            box-shadow: var(--shadow-lg);
            position: relative;
            overflow: hidden;
        }
        
        .report-header::before {
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 300px;
            height: 300px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
        }
        
        .report-header h1 {
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 2.5em;
            font-weight: 700;
            color: #ffffff;
            margin: 0 0 16px 0;
            letter-spacing: -0.02em;
            position: relative;
            z-index: 1;
        }
        
        .report-meta {
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.95em;
            font-weight: 400;
            position: relative;
            z-index: 1;
        }
        
        .report-meta strong {
            font-weight: 600;
            color: #ffffff;
        }
        
        /* Main Content Area */
        .report-content {
            background: var(--bg-secondary);
            border-radius: var(--radius-lg);
            padding: 40px;
            box-shadow: var(--shadow-md);
            border: 1px solid var(--border-light);
        }
        
        .report-content p {
            margin: 16px 0;
            text-align: justify;
            color: var(--text-primary);
        }
        
        .report-content p:first-child {
            margin-top: 0;
        }
        
        .report-content br {
            display: block;
            content: "";
            margin: 8px 0;
        }
        
        /* Headings with Visual Hierarchy */
        h1, h2, h3, h4, h5, h6 {
            font-family: 'Playfair Display', Georgia, serif;
            font-weight: 600;
            letter-spacing: -0.01em;
            margin-top: 0;
        }
        
        h2 {
            font-size: 1.8em;
            color: var(--primary-700);
            margin-top: 48px;
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--primary-200);
            position: relative;
        }
        
        h2::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 80px;
            height: 2px;
            background: linear-gradient(90deg, var(--accent-start), var(--accent-end));
        }
        
        h3 {
            font-size: 1.4em;
            color: var(--primary-600);
            margin-top: 32px;
            margin-bottom: 16px;
            font-weight: 600;
        }
        
        h4, h5, h6 {
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            color: var(--text-primary);
            margin-top: 24px;
            margin-bottom: 12px;
        }
        
        /* Lists with Better Styling */
        .report-content ul, .report-content ol {
            margin: 20px 0;
            padding-left: 28px;
        }
        
        .report-content ul {
            list-style: none;
            padding-left: 24px;
        }
        
        .report-content ul li {
            position: relative;
            margin: 10px 0;
            padding-left: 20px;
        }
        
        .report-content ul li::before {
            content: '';
            position: absolute;
            left: 0;
            top: 10px;
            width: 8px;
            height: 8px;
            background: linear-gradient(135deg, var(--accent-start), var(--accent-end));
            border-radius: 50%;
        }
        
        .report-content ol {
            counter-reset: item;
            list-style: none;
            padding-left: 24px;
        }
        
        .report-content ol li {
            position: relative;
            margin: 10px 0;
            padding-left: 32px;
            counter-increment: item;
        }
        
        .report-content ol li::before {
            content: counter(item);
            position: absolute;
            left: 0;
            top: 2px;
            width: 22px;
            height: 22px;
            background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
            color: white;
            font-size: 0.75em;
            font-weight: 600;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Enhanced Tables */
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 28px 0;
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            border: 1px solid var(--border-color);
        }
        
        thead {
            background: linear-gradient(135deg, var(--primary-600), var(--primary-700));
        }
        
        th {
            color: #ffffff;
            font-weight: 600;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 16px;
            text-align: left;
            border: none;
        }
        
        td {
            padding: 14px 16px;
            border-bottom: 1px solid var(--border-light);
            color: var(--text-primary);
            font-size: 0.95em;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        tbody tr {
            background: var(--bg-secondary);
            transition: all 0.2s ease;
        }
        
        tbody tr:nth-child(even) {
            background: var(--highlight-bg);
        }
        
        tbody tr:hover {
            background: var(--primary-50);
            transform: translateX(4px);
        }
        
        /* Text Formatting */
        strong {
            font-weight: 600;
            color: var(--primary-700);
        }
        
        em {
            font-style: italic;
            color: var(--text-secondary);
        }
        
        /* Inline Code */
        code {
            font-family: 'JetBrains Mono', 'Monaco', 'Menlo', monospace;
            font-size: 0.85em;
            background: var(--code-bg);
            color: var(--primary-700);
            padding: 3px 8px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-color);
        }
        
        /* Code Blocks */
        pre {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: var(--radius);
            padding: 20px;
            margin: 24px 0;
            overflow-x: auto;
            box-shadow: var(--shadow-md);
        }
        
        pre code {
            background: transparent;
            color: #e2e8f0;
            border: none;
            padding: 0;
            font-size: 0.9em;
            line-height: 1.6;
        }
        
        /* Blockquotes */
        blockquote {
            margin: 24px 0;
            padding: 20px 24px;
            background: linear-gradient(135deg, var(--primary-50) 0%, var(--bg-secondary) 100%);
            border-left: 4px solid var(--primary-500);
            border-radius: 0 var(--radius) var(--radius) 0;
            font-style: italic;
            color: var(--text-secondary);
            box-shadow: var(--shadow-sm);
        }
        
        blockquote p {
            margin: 0;
        }
        
        /* Rating Badges */
        .rating-strong-buy, .rating-buy, .rating-hold, .rating-sell, .rating-avoid {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            box-shadow: var(--shadow-sm);
        }
        
        .rating-strong-buy {
            background: var(--success-bg);
            color: #047857;
        }
        
        .rating-buy {
            background: linear-gradient(135deg, #d1fae5, #a7f3d0);
            color: #047857;
        }
        
        .rating-hold {
            background: var(--warning-bg);
            color: #b45309;
        }
        
        .rating-sell, .rating-avoid {
            background: var(--danger-bg);
            color: #b91c1c;
        }
        
        /* Highlight Effect */
        .highlight {
            background: linear-gradient(120deg, #fef3c7 0%, #fde68a 100%);
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 500;
        }
        
        /* Links */
        a {
            color: var(--primary-600);
            text-decoration: none;
            border-bottom: 1px solid transparent;
            transition: all 0.2s ease;
        }
        
        a:hover {
            color: var(--primary-700);
            border-bottom-color: var(--primary-300);
        }
        
        /* Horizontal Rule */
        hr {
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--border-color), transparent);
            margin: 40px 0;
        }
        
        /* Footer */
        .footer {
            margin-top: 60px;
            padding: 30px;
            background: var(--bg-secondary);
            border-radius: var(--radius);
            border: 1px solid var(--border-light);
            text-align: center;
            color: var(--text-tertiary);
            font-size: 0.9em;
            box-shadow: var(--shadow-sm);
        }
        
        /* Section Cards (for future use) */
        .section-card {
            background: var(--bg-secondary);
            border-radius: var(--radius);
            padding: 28px;
            margin: 24px 0;
            border: 1px solid var(--border-light);
            box-shadow: var(--shadow-sm);
            transition: all 0.3s ease;
        }
        
        .section-card:hover {
            box-shadow: var(--shadow-md);
            transform: translateY(-2px);
        }
        
        /* Metric Cards */
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 24px 0;
        }
        
        .metric-card {
            background: linear-gradient(135deg, var(--bg-secondary) 0%, var(--primary-50) 100%);
            border-radius: var(--radius);
            padding: 20px;
            border: 1px solid var(--border-light);
            text-align: center;
        }
        
        .metric-value {
            font-family: 'Playfair Display', serif;
            font-size: 2em;
            font-weight: 700;
            color: var(--primary-600);
        }
        
        .metric-label {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-top: 4px;
        }
        
        /* Print Styles */
        @media print {
            body {
                background: white;
                padding: 20px;
            }
            
            .report-header {
                box-shadow: none;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }
            
            .report-content {
                box-shadow: none;
                border: 1px solid #ddd;
            }
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .report-header, .report-content, h2, table {
            animation: fadeIn 0.6s ease-out;
        }
    </style>
    """
    
    def render(self, report: Report) -> str:
        """Render report as styled HTML."""
        try:
            import markdown2
            has_markdown2 = True
        except ImportError:
            has_markdown2 = False
        
        # Get markdown content first
        markdown_content = report.content
        if not markdown_content:
            # Build from sections
            lines = []
            section_order = [
                ReportSection.OVERVIEW,
                ReportSection.MACRO,
                ReportSection.TECHNICAL,
                ReportSection.FUNDAMENTAL,
                ReportSection.MULTI_LENS,
                ReportSection.RISK,
                ReportSection.POSITION,
                ReportSection.RATING,
            ]
            for section in section_order:
                content = report.sections.get(section, "")
                if content:
                    lines.append(content)
            markdown_content = "\n\n".join(lines)
        
        # Convert markdown to HTML
        if has_markdown2:
            import markdown2
            html_content = markdown2.markdown(
                markdown_content,
                extras=['tables', 'fenced-code-blocks', 'header-ids', 'break-on-newline']
            )
            # Post-process: apply rating badges and clean up any markdown residues
            html_content = self._apply_rating_badges_to_html(html_content)
            html_content = self._cleanup_markdown_residues(html_content)
        else:
            html_content = self._simple_markdown_to_html(markdown_content)
        
        # Build complete HTML document
        html_parts = [
            "<!DOCTYPE html>",
            "<html lang=\"zh-CN\">",
            "<head>",
            "    <meta charset=\"UTF-8\">",
            "    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">",
            f"    <title>{report.metadata.title}</title>",
            self.DEFAULT_CSS,
            "</head>",
            "<body>",
            "    <div class=\"report-header\">",
            f"        <h1>{report.metadata.title}</h1>",
            "        <div class=\"report-meta\">",
            f"            <strong>{report.company_name}</strong> ({report.ticker}) | ",
            f"            Generated: {report.metadata.created_at} | ",
            f"            By: {report.metadata.author}",
            "        </div>",
            "    </div>",
            "    <div class=\"report-content\">",
            html_content,
            "    </div>",
            "    <div class=\"footer\">",
            "        <p>This report is generated by AI for informational purposes only. ",
            "        It does not constitute investment advice.</p>",
            "    </div>",
            "</body>",
            "</html>",
        ]
        
        return "\n".join(html_parts)
    
    def get_content_type(self) -> str:
        """Get MIME type for HTML."""
        return "text/html"
    
    def _simple_markdown_to_html(self, text: str) -> str:
        """
        Simple markdown to HTML conversion when markdown2 is not available.
        Basic support for headers, bold, italic, lists, tables, paragraphs, and line breaks.
        """
        import re
        
        # Escape HTML
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Process by blocks (paragraphs)
        blocks = text.split('\n\n')
        result_blocks = []
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            
            # Headers (must check before other processing)
            if re.match(r'^#{1,6} ', block):
                block = re.sub(r'^###### (.+)$', r'<h6>\1</h6>', block, flags=re.MULTILINE)
                block = re.sub(r'^##### (.+)$', r'<h5>\1</h5>', block, flags=re.MULTILINE)
                block = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', block, flags=re.MULTILINE)
                block = re.sub(r'^### (.+)$', r'<h3>\1</h3>', block, flags=re.MULTILINE)
                block = re.sub(r'^## (.+)$', r'<h2>\1</h2>', block, flags=re.MULTILINE)
                block = re.sub(r'^# (.+)$', r'<h1>\1</h1>', block, flags=re.MULTILINE)
                result_blocks.append(block)
                continue
            
            # Code blocks
            if block.startswith('```'):
                block = '<pre><code>Code Block</code></pre>'
                result_blocks.append(block)
                continue
            
            # Check for tables (lines starting with |)
            lines = block.split('\n')
            has_table = any(line.strip().startswith('|') for line in lines)
            
            if has_table:
                # Process as table
                table_html = self._convert_table_to_html(lines)
                if table_html:
                    result_blocks.append(table_html)
                    continue
            
            # Process lists within the block
            has_list = any(re.match(r'^[\*\-\+] |^\d+\. ', line.strip()) for line in lines)
            
            if has_list:
                # Process as list block
                result_lines = []
                in_ul = False
                in_ol = False
                
                for line in lines:
                    stripped = line.strip()
                    ul_match = re.match(r'^[\*\-\+] (.+)$', stripped)
                    ol_match = re.match(r'^(\d+)\. (.+)$', stripped)
                    
                    if ul_match:
                        if not in_ul:
                            if in_ol:
                                result_lines.append('</ol>')
                                in_ol = False
                            result_lines.append('<ul>')
                            in_ul = True
                        content = ul_match.group(1)
                        # Apply inline formatting
                        content = self._apply_inline_formatting(content)
                        result_lines.append(f'<li>{content}</li>')
                    elif ol_match:
                        if not in_ol:
                            if in_ul:
                                result_lines.append('</ul>')
                                in_ul = False
                            result_lines.append('<ol>')
                            in_ol = True
                        content = ol_match.group(2)
                        content = self._apply_inline_formatting(content)
                        result_lines.append(f'<li>{content}</li>')
                    else:
                        # Non-list line
                        if in_ul:
                            result_lines.append('</ul>')
                            in_ul = False
                        if in_ol:
                            result_lines.append('</ol>')
                            in_ol = False
                        if stripped:
                            line = self._apply_inline_formatting(line)
                            result_lines.append(line + '<br>')
                
                # Close open lists
                if in_ul:
                    result_lines.append('</ul>')
                if in_ol:
                    result_lines.append('</ol>')
                
                result_blocks.append('\n'.join(result_lines))
            else:
                # Regular paragraph with inline formatting
                block = self._apply_inline_formatting(block)
                # Convert line breaks to <br>
                block = block.replace('\n', '<br>\n')
                result_blocks.append(f'<p>{block}</p>')
        
        return '\n\n'.join(result_blocks)
    
    def _convert_table_to_html(self, lines: list) -> str:
        """
        Convert markdown table lines to HTML table.
        
        Args:
            lines: List of lines in the table block
            
        Returns:
            HTML table string or empty string if not a valid table
        """
        import re
        
        # Filter table-related lines
        table_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('|'):
                table_lines.append(stripped)
        
        if len(table_lines) < 2:
            return ''
        
        # Check if second line is a separator (contains only |, -, : and spaces)
        separator_pattern = re.compile(r'^[\|\s\-:]+$')
        has_separator = separator_pattern.match(table_lines[1]) is not None
        
        html_parts = ['<table>']
        
        # Process header row
        header_line = table_lines[0]
        header_cells = [cell.strip() for cell in header_line.split('|')[1:-1]]
        
        html_parts.append('  <thead>')
        html_parts.append('    <tr>')
        for cell in header_cells:
            cell = self._apply_inline_formatting(cell)
            html_parts.append(f'      <th>{cell}</th>')
        html_parts.append('    </tr>')
        html_parts.append('  </thead>')
        
        # Process body rows
        start_idx = 2 if has_separator else 1
        if start_idx < len(table_lines):
            html_parts.append('  <tbody>')
            for line in table_lines[start_idx:]:
                # Skip separator-like lines
                if separator_pattern.match(line):
                    continue
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if cells:
                    html_parts.append('    <tr>')
                    for cell in cells:
                        cell = self._apply_inline_formatting(cell)
                        html_parts.append(f'      <td>{cell}</td>')
                    html_parts.append('    </tr>')
            html_parts.append('  </tbody>')
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def _apply_inline_formatting(self, text: str) -> str:
        """Apply inline formatting (bold, italic, code) and rating badges."""
        import re
        # Bold and italic
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Inline code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Rating badges
        text = self._apply_rating_badges(text)
        return text
    
    def _apply_rating_badges(self, text: str) -> str:
        """Convert rating text to styled badges."""
        import re
        
        # Define ratings with their patterns and unique placeholders
        # Order matters: process longer/more specific patterns first
        ratings = [
            (r'\b(强烈买入|Strong Buy|STRONG BUY)\b', 'rating-strong-buy', 'RATING_SB'),
            (r'\b(买入|Buy|BUY)\b', 'rating-buy', 'RATING_B'),
            (r'\b(观望|Hold|HOLD|中性|Neutral|NEUTRAL)\b', 'rating-hold', 'RATING_H'),
            (r'\b(减持|Underweight|UNDERWEIGHT)\b', 'rating-sell', 'RATING_UW'),
            (r'\b(卖出|Sell|SELL)\b', 'rating-sell', 'RATING_S'),
            (r'\b(回避|Avoid|AVOID)\b', 'rating-avoid', 'RATING_A'),
        ]
        
        # First pass: replace with placeholders
        placeholders = {}
        placeholder_counter = 0
        
        for pattern, css_class, prefix in ratings:
            def replace_with_placeholder(match):
                nonlocal placeholder_counter
                placeholder = f'__{prefix}_{placeholder_counter}__'
                placeholder_counter += 1
                placeholders[placeholder] = f'<span class="{css_class}">{match.group(1)}</span>'
                return placeholder
            
            text = re.sub(pattern, replace_with_placeholder, text, flags=re.IGNORECASE)
        
        # Second pass: replace placeholders with actual HTML
        for placeholder, html in placeholders.items():
            text = text.replace(placeholder, html)
        
        return text
    
    def _apply_rating_badges_to_html(self, html: str) -> str:
        """
        Apply rating badges to HTML content (for markdown2 output).
        Only converts text content, not inside HTML tags.
        """
        import re
        
        # Define ratings - most specific first
        ratings = [
            (r'\b(强烈买入|Strong Buy|STRONG BUY)\b', 'rating-strong-buy'),
            (r'\b(买入|Buy|BUY)\b', 'rating-buy'),
            (r'\b(观望|Hold|HOLD|中性|Neutral|NEUTRAL)\b', 'rating-hold'),
            (r'\b(减持|Underweight|UNDERWEIGHT)\b', 'rating-sell'),
            (r'\b(卖出|Sell|SELL)\b', 'rating-sell'),
            (r'\b(回避|Avoid|AVOID)\b', 'rating-avoid'),
        ]
        
        # Pattern to match text content outside of HTML tags
        # This matches: >text content< (between HTML tags)
        def replace_in_text_content(match):
            text = match.group(1)
            for pattern, css_class in ratings:
                text = re.sub(pattern, lambda m: f'<span class="{css_class}">{m.group(1)}</span>', 
                             text, flags=re.IGNORECASE)
            return '>' + text + '<'
        
        # Replace in text content between tags
        html = re.sub(r'>([^<]+)<', replace_in_text_content, html)
        
        return html
    
    def _cleanup_markdown_residues(self, html: str) -> str:
        """
        Clean up any remaining markdown syntax that wasn't converted.
        This is a safety net for edge cases.
        """
        import re
        
        # Replace any remaining **text** with <strong>text</strong>
        # But be careful not to touch already converted content
        def replace_bold(match):
            content = match.group(1)
            # Skip if already inside HTML tags
            if '<' in content or '>' in content:
                return match.group(0)
            return f'<strong>{content}</strong>'
        
        html = re.sub(r'\*\*([^<*]+?)\*\*', replace_bold, html)
        
        # Replace any remaining *text* with <em>text</em>
        def replace_italic(match):
            content = match.group(1)
            # Skip if already inside HTML tags
            if '<' in content or '>' in content:
                return match.group(0)
            return f'<em>{content}</em>'
        
        html = re.sub(r'(?<!\*)\*([^<*]+?)\*(?!\*)', replace_italic, html)
        
        return html


class JsonRenderer(BaseRenderer):
    """
    Renderer for JSON format.
    
    Outputs structured data for API consumption.
    """
    
    format = ReportFormat.JSON
    
    def render(self, report: Report) -> str:
        """Render report as JSON."""
        data = report.to_dict()
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)
    
    def get_content_type(self) -> str:
        """Get MIME type for JSON."""
        return "application/json"


class TextRenderer(BaseRenderer):
    """
    Renderer for plain text format.
    
    Simple text output without formatting.
    """
    
    format = ReportFormat.TXT
    
    def render(self, report: Report) -> str:
        """Render report as plain text."""
        lines = [
            f"{'=' * 60}",
            f"{report.metadata.title}",
            f"{'=' * 60}",
            "",
            f"Company: {report.company_name} ({report.ticker})",
            f"Date: {report.metadata.created_at}",
            f"Author: {report.metadata.author}",
            "",
            f"{'-' * 60}",
            "",
        ]
        
        if report.content:
            # Strip markdown syntax for plain text
            content = self._strip_markdown(report.content)
            lines.append(content)
        else:
            # Build from sections
            section_order = [
                ReportSection.OVERVIEW,
                ReportSection.MACRO,
                ReportSection.TECHNICAL,
                ReportSection.FUNDAMENTAL,
                ReportSection.MULTI_LENS,
                ReportSection.RISK,
                ReportSection.POSITION,
                ReportSection.RATING,
            ]
            for section in section_order:
                content = report.sections.get(section, "")
                if content:
                    lines.append(self._strip_markdown(content))
                    lines.append("")
        
        lines.extend([
            "",
            f"{'=' * 60}",
            "DISCLAIMER: This report is for informational purposes only.",
            "It does not constitute investment advice.",
            f"{'=' * 60}",
        ])
        
        return "\n".join(lines)
    
    def _strip_markdown(self, text: str) -> str:
        """Simple markdown stripping for plain text output."""
        import re
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Convert headers
        text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
        
        # Convert bold/italic
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        
        # Convert code blocks
        text = re.sub(r'```[\s\S]*?```', '[Code Block]', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        
        # Convert links
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
        
        # Convert tables (simplified)
        text = re.sub(r'\|', ' | ', text)
        text = re.sub(r'\n-{3,}\n', '\n', text)
        
        return text.strip()
    
    def get_content_type(self) -> str:
        """Get MIME type for plain text."""
        return "text/plain"


# Registry of default renderers
def get_default_renderers() -> Dict[ReportFormat, BaseRenderer]:
    """Get dictionary of default renderer instances."""
    return {
        ReportFormat.MARKDOWN: MarkdownRenderer(),
        ReportFormat.HTML: HtmlRenderer(),
        ReportFormat.JSON: JsonRenderer(),
        ReportFormat.TXT: TextRenderer(),
    }
