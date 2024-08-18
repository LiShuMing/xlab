#include "../include/fwd.h"

/**
 * LeetCode 212: Word Search II
 * 
 * Given an m x n board of characters and a list of words, find all words
 * that can be formed by sequences of adjacent (horizontal/vertical) letters.
 * 
 * Optimization: Use Trie + DFS with early termination
 * - Build Trie from all words to enable prefix sharing
 * - Prune search when current path is not a valid prefix
 * - Remove found words to avoid redundant searches
 * 
 * Time: O(m*n*4*l) vs naive O(m*n*k*l)
 */
class TrieNode {
public:
    unordered_map<char, TrieNode*> children;
    string word = "";  // Store complete word if this node marks end
    
    ~TrieNode() {
        for (auto& p : children) {
            delete p.second;
        }
    }
};

class Solution {
private:
    TrieNode* root;
    int m, n;
    vector<string> result;
    vector<vector<char>> board;
    vector<int> dirs = {0, 1, 0, -1, 0};
    
    void buildTrie(const vector<string>& words) {
        root = new TrieNode();
        for (const string& word : words) {
            TrieNode* node = root;
            for (char c : word) {
                if (!node->children.count(c)) {
                    node->children[c] = new TrieNode();
                }
                node = node->children[c];
            }
            node->word = word;  // Mark end of word
        }
    }
    
    void backtrack(int i, int j, TrieNode* parent) {
        char letter = board[i][j];
        TrieNode* currNode = parent->children[letter];
        
        // Check if current path forms a complete word
        if (!currNode->word.empty()) {
            result.push_back(currNode->word);
            currNode->word = "";  // Avoid duplicate results
            // Note: Don't delete node, continue to find longer words
        }
        
        // Mark as visited
        board[i][j] = '#';
        
        // Explore 4 directions
        for (int d = 0; d < 4; d++) {
            int ni = i + dirs[d];
            int nj = j + dirs[d + 1];
            
            // Skip if out of bounds or no matching child in Trie
            if (ni < 0 || ni >= m || nj < 0 || nj >= n) continue;
            if (!currNode->children.count(board[ni][nj])) continue;
            
            backtrack(ni, nj, currNode);
        }
        
        // Restore cell and prune dead branch
        board[i][j] = letter;
        if (currNode->children.empty()) {
            parent->children.erase(letter);  // Prune to speed up future searches
            delete currNode;
        }
    }
    
public:
    vector<string> findWords(vector<vector<char>>& board_, vector<string>& words) {
        board = board_;
        m = board.size();
        n = board[0].size();
        result.clear();
        
        if (m == 0 || n == 0 || words.empty()) return result;
        
        // Build Trie from all words
        buildTrie(words);
        
        // Start DFS from every cell that matches a word prefix
        for (int i = 0; i < m; i++) {
            for (int j = 0; j < n; j++) {
                if (root->children.count(board[i][j])) {
                    backtrack(i, j, root);
                }
            }
        }
        
        delete root;
        return result;
    }
};

// Test
int main() {
    Solution solution;
    
    // Test case 1
    vector<vector<char>> board1 = {
        {'o', 'a', 'a', 'n'},
        {'e', 't', 'a', 'e'},
        {'i', 'h', 'k', 'r'},
        {'i', 'f', 'l', 'v'}
    };
    vector<string> words1 = {"oath", "pea", "eat", "rain", "oak"};
    vector<string> result1 = solution.findWords(board1, words1);
    cout << "Test 1: ";
    for (const string& w : result1) cout << w << " ";
    cout << endl;
    
    // Test case 2 - single word
    vector<vector<char>> board2 = {{'a'}};
    vector<string> words2 = {"a"};
    vector<string> result2 = solution.findWords(board2, words2);
    cout << "Test 2: ";
    for (const string& w : result2) cout << w << " ";
    cout << endl;
    
    // Test case 3 - duplicate words in result
    vector<vector<char>> board3 = {
        {'a', 'a', 'a'},
        {'a', 'a', 'a'},
        {'a', 'a', 'a'}
    };
    vector<string> words3 = {"aa"};
    vector<string> result3 = solution.findWords(board3, words3);
    cout << "Test 3: ";
    for (const string& w : result3) cout << w << " ";
    cout << endl;
    
    return 0;
}
