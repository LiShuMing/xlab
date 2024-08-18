use std::collections::HashSet;
use std::sync::OnceLock;

/// Extracted entity with type and text.
pub type Entity = (String, String); // (entity_type, entity_text)

/// Extract entities from text using rules.
/// MVP: regex patterns for dates, emails, URLs + a small dictionary for common names.
pub fn extract_entities(text: &str) -> Vec<Entity> {
    let mut entities = Vec::new();
    let mut seen = HashSet::new();

    // Cached regexes for email, URL, and date matching
    static EMAIL_RE: OnceLock<regex_lite::Regex> = OnceLock::new();
    static URL_RE: OnceLock<regex_lite::Regex> = OnceLock::new();
    static DATE_RE: OnceLock<regex_lite::Regex> = OnceLock::new();

    // Email pattern
    let email_re = EMAIL_RE.get_or_init(|| {
        regex_lite::Regex::new(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
            .expect("valid email regex")
    });
    for m in email_re.find_iter(text) {
        let key = ("EMAIL".to_string(), m.as_str().to_string());
        if seen.insert(format!("EMAIL:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // URL pattern
    let url_re = URL_RE.get_or_init(|| {
        regex_lite::Regex::new(r"https?://[^\s]+").expect("valid url regex")
    });
    for m in url_re.find_iter(text) {
        let key = ("URL".to_string(), m.as_str().to_string());
        if seen.insert(format!("URL:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // Date pattern (ISO: 2026-05-18, US: 05/18/2026)
    let date_re = DATE_RE.get_or_init(|| {
        regex_lite::Regex::new(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}")
            .expect("valid date regex")
    });
    for m in date_re.find_iter(text) {
        let key = ("DATE".to_string(), m.as_str().to_string());
        if seen.insert(format!("DATE:{}", m.as_str())) {
            entities.push(key);
        }
    }

    // Simple dictionary: match common English first names (small list for MVP)
    // Uses word-boundary regex to avoid false positives (e.g., "Bobby" ≠ "Bob")
    const COMMON_NAMES: &[&str] = &[
        "Bob", "Alice", "John", "Mary", "David", "Sarah", "Michael", "Emma",
        "James", "Linda", "Robert", "Jennifer", "William", "Lisa", "Richard",
    ];
    for name in COMMON_NAMES {
        // (?i) case-insensitive, \b word boundary
        let pattern = format!(r"(?i)\b{}\b", regex_lite::escape(name));
        let name_re = regex_lite::Regex::new(&pattern).expect("valid name regex");
        if name_re.is_match(text) && seen.insert(format!("PERSON:{}", name)) {
            entities.push(("PERSON".to_string(), name.to_string()));
        }
    }

    entities
}

/// Batch extract entities from multiple texts.
/// Returns one Vec<Entity> per input text (parallel arrays).
pub fn extract_entities_batch(texts: &[&str]) -> Vec<Vec<Entity>> {
    texts.iter().map(|t| extract_entities(t)).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_email() {
        let entities = extract_entities("Contact Bob at bob@example.com for more info");
        assert!(entities.iter().any(|(t, v)| t == "EMAIL" && v == "bob@example.com"));
        assert!(entities.iter().any(|(t, v)| t == "PERSON" && v == "Bob"));
    }

    #[test]
    fn test_extract_date() {
        let entities = extract_entities("Meeting on 2026-05-18");
        assert!(entities.iter().any(|(t, v)| t == "DATE" && v == "2026-05-18"));
    }

    #[test]
    fn test_no_duplicates() {
        let entities = extract_entities("bob@x.com bob@x.com");
        let emails: Vec<_> = entities.iter().filter(|(t, _)| t == "EMAIL").collect();
        assert_eq!(emails.len(), 1);
    }

    #[test]
    fn test_extract_url() {
        let entities = extract_entities("Check https://example.com/page for details");
        assert!(entities.iter().any(|(t, v)| t == "URL" && v == "https://example.com/page"));
    }

    #[test]
    fn test_extract_empty() {
        let entities = extract_entities("");
        assert!(entities.is_empty());
    }

    #[test]
    fn test_extract_no_entities() {
        let entities = extract_entities("just a normal sentence with nothing special");
        assert!(entities.is_empty());
    }

    #[test]
    fn test_extract_batch() {
        let texts = vec!["alice@x.com", "bob@y.com"];
        let results = extract_entities_batch(&texts);
        assert_eq!(results.len(), 2);
        assert!(results[0].iter().any(|(t, v)| t == "EMAIL" && v == "alice@x.com"));
        assert!(results[1].iter().any(|(t, v)| t == "EMAIL" && v == "bob@y.com"));
    }

    #[test]
    fn test_false_positive_name() {
        // "Bobby" should NOT match "Bob"
        let entities = extract_entities("Bobby went to the store");
        assert!(!entities.iter().any(|(t, v)| t == "PERSON" && v == "Bob"));
    }

    #[test]
    fn test_case_insensitive_name() {
        // "bob" and "ALICE" should match
        let entities = extract_entities("bob and ALICE met");
        assert!(entities.iter().any(|(t, v)| t == "PERSON" && v == "Bob"));
        assert!(entities.iter().any(|(t, v)| t == "PERSON" && v == "Alice"));
    }

    #[test]
    fn test_name_with_punctuation() {
        // "Bob." at end of sentence should match
        let entities = extract_entities("I talked to Bob.");
        assert!(entities.iter().any(|(t, v)| t == "PERSON" && v == "Bob"));
    }
}
