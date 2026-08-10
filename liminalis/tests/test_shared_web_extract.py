from __future__ import annotations

from backend._shared.web_extract import extract_article, html_to_text


def test_extract_article_prefers_trafilatura_metadata() -> None:
    long_content = " ".join(["shared extraction content"] * 30)
    html = f"""
    <html>
      <head>
        <title>Document title</title>
        <meta property="article:published_time" content="2026-01-01" />
      </head>
      <body>
        <nav>navigation noise</nav>
        <article>
          <h1>Shared extraction article</h1>
          <p>{long_content}</p>
        </article>
      </body>
    </html>
    """

    article = extract_article(html, url="https://example.test/article")

    assert article is not None
    assert article.engine == "trafilatura"
    assert article.title == "Shared extraction article"
    assert article.published_at == "2026-01-01"
    assert "shared extraction content" in article.text
    assert "navigation noise" not in article.text


def test_html_to_text_removes_boilerplate_tags() -> None:
    text = html_to_text("<main>Hello <script>bad()</script><nav>menu</nav>World</main>")

    assert text == "Hello World"
