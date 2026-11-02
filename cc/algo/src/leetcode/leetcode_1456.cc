#include "../include/fwd.h"

class Solution {
public:
    int maxVowels(string s, int k) {
        unordered_set<char> vowels = {'a', 'e', 'i', 'o', 'u'};
        int count = 0;
        for (int i = 0; i < k; i++) {
            if (vowels.count(s[i])) {
                count++;
            }
        }
        int max_count = count;
        for (int i = k; i < s.size(); i++) {
            if (vowels.count(s[i])) {
                count++;
            }
            if (vowels.count(s[i - k])) {
                count--;
            }
            max_count = max(max_count, count);
        }
        return max_count;
    }
};