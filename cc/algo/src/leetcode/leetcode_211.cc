#include "../include/fwd.h"
class WordDictionary {
private:
    class TrieNode {
    public:
        TrieNode* children[26];
        bool isEnd;
        TrieNode() {
            isEnd = false;
            memset(children, 0, sizeof(children));
        }
    };
    TrieNode* root;

public:
    WordDictionary() { root = new TrieNode(); }

    void addWord(string word) {
        TrieNode* node = root;
        for (char ch : word) {
            if (!node->children[ch - 'a']) {
                node->children[ch - 'a'] = new TrieNode();
            }
            node = node->children[ch - 'a'];
        }
        node->isEnd = true;
    }

    bool search(string word) { return search(word, 0, root); }
    bool search(string word, int index, TrieNode* node) {
        if (index == word.size()) return node->isEnd;
        if (word[index] == '.') {
            for (auto& child : node->children) {
                if (child && search(word, index + 1, child)) return true;
            }
            return false;
        } else {
            return node->children[word[index] - 'a'] &&
                   search(word, index + 1, node->children[word[index] - 'a']);
        }
    }
};

int main() {
    WordDictionary wordDictionary;
    wordDictionary.addWord("bad");
    wordDictionary.addWord("dad");
    wordDictionary.addWord("mad");
    cout << wordDictionary.search("pad") << endl;
    cout << wordDictionary.search("bad") << endl;
    cout << wordDictionary.search(".ad") << endl;
    cout << wordDictionary.search("b..") << endl;
    return 0;
}