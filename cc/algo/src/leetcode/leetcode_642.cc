#include "../include/fwd.h"

/**
Design a search autocomplete system for a search engine. Users may input a sentence (at least one word and end with a special character '#').

You are given a string array sentences and an integer array times both of length n where sentences[i] is a previously typed sentence and times[i] is the corresponding number of times the sentence was typed. For each input character (except '#'), return the top 3 historical hot sentences that have the same prefix as the part of the sentence already typed.

Here are the specific rules:

1. The hot degree for a sentence is defined as the number of times a user typed the exactly same sentence before.
2. The returned top 3 hot sentences should be sorted by hot degree (The first is the hottest one). If several sentences have the same degree of hot, you need to use ASCII-code order (smaller one appears first).
3. If less than 3 hot sentences exist, return as many as you can.
4. When the input is a special character '#', it means the sentence ends, and the sentence just typed should be saved as a historical sentence.

Implement the AutocompleteSystem class:

- AutocompleteSystem(String[] sentences, int[] times) Initializes the object with the sentences and times arrays.
- List<String> input(char c) This indicates that the user typed the character c.
    - If c == '#', save the sentence and return an empty list.
    - Otherwise, return the top 3 historical hot sentences that have the same prefix as the part of the sentence already typed. The returned sentences should be sorted as described above.

Example 1:
Input:
["AutocompleteSystem", "input", "input", "input", "input"]
[[["i love you", "island", "iroman", "i love leetcode"], [5, 3, 2, 2]], ["i"], [" "], ["a"], ["#"]]

Output:
[null, ["i love you", "island", "i love leetcode"], ["i love you", "i love leetcode"], [], []]

Explanation:
AutocompleteSystem obj = new AutocompleteSystem(["i love you", "island", "iroman", "i love leetcode"], [5, 3, 2, 2]);
obj.input("i"); // return ["i love you", "island", "i love leetcode"].
                // There are four sentences that have prefix "i". Among them, "ironman" and "i love leetcode" have same hot degree. Since "i love leetcode" has a lower ASCII order, it comes before "ironman".
                // Also we only need to output top 3 hot sentences, so "ironman" will be ignored.
obj.input(" "); // return ["i love you", "i love leetcode"].
obj.input("a"); // return []. There are no sentences that have prefix "i a".
obj.input("#"); // return []. Then the system saves "i a" as a historical sentence.
 */
class AutocompleteSystem {
private:
    struct TrieNode {
        unordered_map<char, TrieNode*> children;
        int count;
        string sentence;  // Store the complete sentence at the end node
        TrieNode() : count(0) {}
    };
    
    TrieNode* root;
    string currentSentence;
    
    void insert(const string& sentence, int time) {
        TrieNode* node = root;
        for (size_t i = 0; i < sentence.size(); i++) {
            char ch = sentence[i];
            if (!node->children.count(ch)) {
                node->children[ch] = new TrieNode();
            }
            node = node->children[ch];
        }
        node->count += time;
        node->sentence = sentence;
    }
    
    void dfs(TrieNode* node, vector<pair<int, string> >& candidates) {
        if (node->count > 0) {
            candidates.push_back(make_pair(-node->count, node->sentence));  // Negative for descending order
        }
        for (unordered_map<char, TrieNode*>::iterator it = node->children.begin(); 
             it != node->children.end(); ++it) {
            dfs(it->second, candidates);
        }
    }
    
    vector<string> getTop3(const string& prefix) {
        TrieNode* node = root;
        // Navigate to the prefix node
        for (char ch : prefix) {
            if (!node->children.count(ch)) {
                return vector<string>();
            }
            node = node->children[ch];
        }
        
        // Collect all candidates with their counts
        vector<pair<int, string> > candidates;
        dfs(node, candidates);
        
        // Sort: first by count (ascending, since we used negative), then by string (ascending)
        sort(candidates.begin(), candidates.end());
        
        // Get top 3
        vector<string> result;
        for (int i = 0; i < min(3, (int)candidates.size()); i++) {
            result.push_back(candidates[i].second);
        }
        return result;
    }
    
public:
    AutocompleteSystem(vector<string>& sentences, vector<int>& times) {
        root = new TrieNode();
        currentSentence = "";
        for (int i = 0; i < sentences.size(); i++) {
            insert(sentences[i], times[i]);
        }
    }
    
    vector<string> input(char c) {
        if (c == '#') {
            // Save the current sentence
            if (!currentSentence.empty()) {
                insert(currentSentence, 1);
            }
            currentSentence = "";
            return vector<string>();
        }
        
        // Append character to current sentence
        currentSentence += c;
        
        // Return top 3 suggestions
        return getTop3(currentSentence);
    }
};

int main() {
    vector<string> sentences;
    sentences.push_back("i love you");
    sentences.push_back("island");
    sentences.push_back("iroman");
    sentences.push_back("i love leetcode");
    
    vector<int> times;
    times.push_back(5);
    times.push_back(3);
    times.push_back(2);
    times.push_back(2);
    
    AutocompleteSystem* obj = new AutocompleteSystem(sentences, times);
    
    vector<string> result1 = obj->input('i');
    cout << "Input 'i': ";
    for (size_t i = 0; i < result1.size(); i++) {
        cout << result1[i] << " ";
    }
    cout << endl;
    
    vector<string> result2 = obj->input(' ');
    cout << "Input ' ': ";
    for (size_t i = 0; i < result2.size(); i++) {
        cout << result2[i] << " ";
    }
    cout << endl;
    
    vector<string> result3 = obj->input('a');
    cout << "Input 'a': ";
    for (size_t i = 0; i < result3.size(); i++) {
        cout << result3[i] << " ";
    }
    cout << endl;
    
    vector<string> result4 = obj->input('#');
    cout << "Input '#': (empty)" << endl;
    
    return 0;
}