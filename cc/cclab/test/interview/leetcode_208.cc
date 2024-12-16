#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

using namespace std;

class Leetcode208Test : public testing::Test {};
class Trie {
private:
    class Node {
    public:
        unordered_map<char, Node*> next;
        bool is_end;
        Node() {
            is_end = false;
        }
    };
    Node* root;
public:
    Trie() {
        root = new Node();
    }
    
    void insert(string word) {
        Node* cur = root;
        for (char ch : word) {
            auto& next = cur->next;
            if (!next.count(ch)) {
                Node* node = new Node();
                next.insert({ch, node});
                cur = node;
            } else {
                cur = next[ch];
            }
        }
        cur->is_end = true;
    }
    
    bool search(string word) {
        Node* cur = root;
        for (auto ch : word) {
            auto& next = cur->next;
            if (next.count(ch)) {
                cur = next[ch];
            } else {
                return false;
            }
        }
        return cur->is_end;
    }
    
    bool startsWith(string prefix) {
        Node* cur = root;
        for (char ch : prefix) {
            auto& next = cur->next;
            if (next.count(ch)) {
                cur = next[ch];
            } else {
                return false;
            }
        }
        return true;
    }
};

/**
 * Your Trie object will be instantiated and called as such:
 * Trie* obj = new Trie();
 * obj->insert(word);
 * bool param_2 = obj->search(word);
 * bool param_3 = obj->startsWith(prefix);
 */
/**
 * Your Trie object will be instantiated and called as such:
 * Trie* obj = new Trie();
 * obj->insert(word);
 * bool param_2 = obj->search(word);
 * bool param_3 = obj->startsWith(prefix);
 */
TEST_F(Leetcode208Test, Test1) {
    Trie* obj = new Trie();
    obj->insert("apple");
    ASSERT_TRUE(obj->search("apple"));
    ASSERT_FALSE(obj->search("app"));
    ASSERT_TRUE(obj->startsWith("app"));
    obj->insert("app");
    ASSERT_TRUE(obj->search("app"));
}