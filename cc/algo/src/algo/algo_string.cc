#include "../include/fwd.h"

/**
 * Volnitsky Algorithm (Fast Search)
 * 
 * A linear-time string searching algorithm by Igor Volnitsky.
 * Key idea: Preprocess pattern to skip non-matching characters quickly.
 * 
 * Time Complexity: O(n + m) average case, O(n*m) worst case
 * Space Complexity: O(m + alphabet_size)
 */

#include <cstdint>
#include <cstring>
#include <string>
#include <vector>

class VolnitskySearcher {
public:
    VolnitskySearcher(const std::string& pattern) : pattern_(pattern) {
        size_t m = pattern_.size();
        if (m < 2) return;

        // Use a 64KB hash table to store the last occurrence of each 2-byte sequence
        hash_table_.resize(65536, -1);
        for (int i = 0; i <= static_cast<int>(m) - 2; ++i) {
            uint16_t hash = load_hash(pattern_.data() + i);
            hash_table_[hash] = i;
        }
    }

    const char* search(const char* text, size_t n) {
        size_t m = pattern_.size();
        if (m < 2) return nullptr; // Fallback to simpler search for tiny patterns
        if (n < m) return nullptr;

        const char* end = text + n;
        const char* last_start = text + n - m;  // Last valid starting position
        
        const char* current = text + m - 2;
        const char* hash_end = end - 1;  // Need at least 2 bytes for hash

        while (current <= hash_end) {
            // Check the fingerprint (2-byte) at the current position
            uint16_t hash = load_hash(current);
            int offset = hash_table_[hash];

            if (offset != -1) {
                // Potential match found, verify the full string
                const char* start = current - offset;
                if (start >= text && start <= last_start && memcmp(start, pattern_.data(), m) == 0) {
                    return start;
                }
            }

            // Skip forward by m-1 positions
            current += (m - 1);
        }
        return nullptr;
    }

private:
    static uint16_t load_hash(const void* ptr) {
        uint16_t val;
        memcpy(&val, ptr, 2);
        return val;
    }

    std::string pattern_;
    std::vector<int> hash_table_;
};

class Volnitsky {
public:
    // Find first occurrence of pattern in text
    // Returns -1 if not found
    static int search(const string& text, const string& pattern) {
        if (pattern.empty()) return 0;
        if (text.empty() || pattern.size() > text.size()) return -1;

        size_t m = pattern.size();

        // Build position map: char -> last position in pattern
        vector<int> lastPos(256, -1);
        for (size_t i = 0; i < m; i++) {
            lastPos[(unsigned char)pattern[i]] = i;
        }

        size_t i = 0;
        while (i <= text.size() - m) {
            // Check from end to start
            int j = (int)m - 1;
            while (j >= 0 && text[i + j] == pattern[j]) {
                j--;
            }

            if (j < 0) {
                return i; // Found
            }

            // Mismatch at position j
            // Get last position of this character in pattern
            int charLastPos = lastPos[(unsigned char)text[i + j]];

            if (charLastPos == -1) {
                // Character not in pattern at all, skip whole pattern
                i += m;
            } else {
                // Character exists, shift to align it with its position
                // i += (m - charLastPos) - j
                i += m - charLastPos - j;
            }
        }

        return -1;
    }

    // Find all occurrences
    static vector<int> findAll(const string& text, const string& pattern) {
        vector<int> results;
        if (pattern.empty() || text.empty()) return results;

        // Search from each position to handle overlapping patterns
        size_t searchOffset = 0;
        while (searchOffset < text.size()) {
            int pos = search(text.substr(searchOffset), pattern);
            if (pos == -1) break;

            results.push_back(searchOffset + pos);

            // Move offset by 1 to find overlapping occurrences
            searchOffset += pos + 1;

            // Check if remaining text is too short
            if (searchOffset + pattern.size() > text.size()) break;
        }

        return results;
    }

    // Search with character hashing (optimized version)
    // Uses Bloom filter-like character check for faster rejection
    static int searchOptimized(const string& text, const string& pattern) {
        if (pattern.empty()) return 0;
        if (text.empty() || pattern.size() > text.size()) return -1;

        size_t n = text.size();
        size_t m = pattern.size();

        // Precompute character presence bitmask
        uint64_t charMask = 0;
        for (char c : pattern) {
            charMask |= (1ULL << (c % 64));
        }

        // Build position map: char -> last position in pattern
        vector<int> posMap(256, -1);
        for (int i = (int)m - 1; i >= 0; i--) {
            posMap[(unsigned char)pattern[i]] = i;
        }

        size_t i = 0;
        while (i <= n - m) {
            // Quick char presence check
            if (!(charMask & (1ULL << (text[i + m - 1] % 64)))) {
                i += m;
                continue;
            }

            // Match from end to start
            int j = (int)m - 1;
            while (j >= 0 && text[i + j] == pattern[j]) {
                j--;
            }

            if (j < 0) return i;

            // Calculate shift
            int charPos = posMap[(unsigned char)text[i + j]];
            if (charPos == -1) {
                i += m; // Char not in pattern
            } else {
                i += m - charPos - j;
            }
        }

        return -1;
    }
};

int main() {
    string text = "ABABDABACDABABCABAB";
    string pattern = "ABABCABAB";
    cout << "Text: " << text << endl;
    cout << "Pattern: " << pattern << endl;

    {
        VolnitskySearcher searcher(pattern);
        const char* pos = searcher.search(text.c_str(), text.size());
        cout << "Found at position: " << pos << endl;
    }

    int pos = Volnitsky::search(text, pattern);
    cout << "Found at position: " << pos << endl;

    vector<int> all = Volnitsky::findAll(text, "AB");
    cout << "All 'AB' positions: ";
    for (int p : all) cout << p << " ";
    cout << endl;

    int posOpt = Volnitsky::searchOptimized(text, pattern);
    cout << "Optimized search at position: " << posOpt << endl;

    return 0;
}
