use scraper::{Html, Selector};
use html2text::from_read;

pub async fn fetch_html(url: &str) -> Result<String, String> {
    let client = reqwest::Client::builder()
        .user_agent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        .build()
        .map_err(|e| e.to_string())?;

    let response = client
        .get(url)
        .send()
        .await
        .map_err(|e| format!("Failed to fetch URL: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("HTTP error: {}", response.status()));
    }

    let html = response
        .text()
        .await
        .map_err(|e| e.to_string())?;

    Ok(html)
}

pub fn extract_text(html: &str) -> String {
    // Use html2text for basic text extraction
    let reader = html.as_bytes();
    let text = from_read(reader, 10000); // 10000 chars width

    // Clean up the text
    let cleaned = clean_text(&text);

    cleaned
}

fn clean_text(text: &str) -> String {
    let mut result = String::new();
    let mut in_whitespace = false;

    for c in text.chars() {
        if c.is_whitespace() {
            if !in_whitespace && !result.is_empty() {
                result.push(' ');
                in_whitespace = true;
            }
        } else {
            result.push(c);
            in_whitespace = false;
        }
    }

    // Remove excessive newlines
    let re = regex::Regex::new(r"\n{3,}").unwrap();
    re.replace_all(&result, "\n\n").to_string()
}

pub fn extract_title(html: &str) -> String {
    let fragment = scraper::Html::parse_document(html);
    
    // Try og:title first
    if let Some(title) = extract_meta_property(&fragment, "og:title") {
        return title;
    }
    
    // Try twitter:title
    if let Some(title) = extract_meta_property(&fragment, "twitter:title") {
        return title;
    }
    
    // Fall back to <title>
    let title_selector = Selector::parse("title").unwrap();
    if let Some(title_elem) = fragment.select(&title_selector).next() {
        return title_elem.text().collect::<Vec<_>>().join(" ").trim().to_string();
    }
    
    String::from("Untitled")
}

fn extract_meta_property(fragment: &Html, property: &str) -> Option<String> {
    let selector = Selector::parse(&format!("meta[property=\"{}\"]", property)).unwrap();
    if let Some(meta) = fragment.select(&selector).next() {
        if let Some(content) = meta.value().attr("content") {
            return Some(content.to_string());
        }
    }
    None
}

pub fn estimate_reading_time(text: &str, words_per_minute: usize) -> usize {
    let word_count = text.split_whitespace().count();
    (word_count as f64 / words_per_minute as f64).ceil() as usize
}
