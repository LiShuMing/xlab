#include "../include/fwd.h"

class Solution {
private:
    vector<bool> dp;
    
public:
    vector<string> wordBreak(string s, vector<string>& wordDict) {
        int n = s.size();
        dp.assign(n + 1, false);
        dp[0] = true;
        for (int i = 1; i <= n; i++) {
            for (int j = 0; j < i; j++) {
                if (dp[j] && find(wordDict.begin(), wordDict.end(), s.substr(j, i - j)) != wordDict.end()) {
                    dp[i] = true;
                    break;
                }
            }
        }
        if (!dp[n]) return vector<string>();
        vector<string> result;
        vector<string> path;
        backtrack(s, 0, wordDict, path, result);
        return result;
    }
    
    void backtrack(string& s, int start, vector<string>& wordDict, vector<string>& path, vector<string>& result) {
        if (start == s.size()) {
            // Join all words in path with spaces
            string sentence;
            for (int i = 0; i < path.size(); i++) {
                if (i > 0) sentence += " ";
                sentence += path[i];
            }
            result.push_back(sentence);
            return;
        }
        for (int i = start + 1; i <= s.size(); i++) {
            string word = s.substr(start, i - start);
            if (dp[i] && find(wordDict.begin(), wordDict.end(), word) != wordDict.end()) {
                path.push_back(word);
                backtrack(s, i, wordDict, path, result);
                path.pop_back();
            }
        }
    }
};
int main() {
    Solution solution;
    string s = "leetcode";
    vector<string> wordDict;
    wordDict.push_back("leet");
    wordDict.push_back("code");
    vector<string> result = solution.wordBreak(s, wordDict);
    for (int i = 0; i < result.size(); i++) {
        cout << result[i] << endl;
    }
    return 0;
}