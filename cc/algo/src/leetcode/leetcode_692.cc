#include "../include/fwd.h"
class Solution {
public:
    // when the frequency is the same, we need to sort the words in ascending order
    // use a minheap to store the words with the highest frequency
    struct Compare {
        bool operator()(const pair<int, string>& a, const pair<int, string>& b) {
            if (a.first != b.first) {
                // lower frequency should have lower priority (be popped first)
                return a.first > b.first;
            }
            // when frequency is same, we want lexicographically smaller words in final result
            // For min-heap: return true means a has lower priority
            // We want lexicographically smaller words to appear first after reverse
            return a.second < b.second;
        }
    };
    vector<string> topKFrequent(vector<string>& words, int k) {
        unordered_map<string, int> freq;
        for (const string& word : words) {
            freq[word]++;
        }

        // use a minheap to store the words with the highest frequency
        priority_queue<pair<int, string>, vector<pair<int, string>>, Compare> pq;
        for (auto& [word, count] : freq) {
            pq.push({count, word});
            if (pq.size() > k) {
                pq.pop();
            }
        }
        vector<string> ans;
        while (!pq.empty()) {
            ans.push_back(pq.top().second);
            pq.pop();
        }
        // reverse to get descending order of frequency (highest first)
        reverse(ans.begin(), ans.end());
        return ans;
    }
};

int main() {
    Solution solution;
    vector<string> words = {"i", "love", "leetcode", "i", "love", "coding"};
    int k = 2;
    vector<string> ans = solution.topKFrequent(words, k);
    cout << "ans: ";
    printVector(ans);
    return 0;
}