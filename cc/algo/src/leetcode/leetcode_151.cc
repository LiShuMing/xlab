#include "../include/fwd.h"

class Solution {
public:
    string reverseWords(string s) {
        int n = s.size();
        int l = 0;
        int r = n - 1;

        // find the first non-space character
        while (l < r && s[l] == ' ') l++;
        // find the last non-space character
        while (l < r && s[r] == ' ') r--;

        // use a deque to store the words
        deque<string> words;
        string word;
        while (l <= r) {
            if (s[l] != ' ') {
                word += s[l];
            } else if (!word.empty()) {
                words.push_front(word);
                word.clear();
            }
            l++;
        }
        if (!word.empty()) words.push_front(word);
        // join the words with a space
        string result;
        while (!words.empty()) {
            result += words.front();
            words.pop_front();
            if (!words.empty()) result += ' ';
        }
        return result;
    }
};
