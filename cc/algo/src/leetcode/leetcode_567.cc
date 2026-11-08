#include "../include/fwd.h"


class Solution {
public:
    bool checkInclusion(string s1, string s2) {
        vector<int> cnt(26);
        for (char c : s1) cnt[c - 'a']++;
        int n = s1.size(), m = s2.size();
        if (n > m) return false;  // s1 比 s2 长时窗口永远放不下，直接排除
        for (int i = 0; i < n; i++) cnt[s2[i] - 'a']--;
        // check if all elements in cnt are zero
        if (all_of(cnt.begin(), cnt.end(), [](int x) { return x == 0; })) return true;

        for (int i = n; i < m; i++) {
            cnt[s2[i] - 'a']--;
            cnt[s2[i - n] - 'a']++;
            if (all_of(cnt.begin(), cnt.end(), [](int x) { return x == 0; })) return true;
        }
        return false;
    }
};

int main() {
    Solution s;
    struct Case {
        string s1;
        string s2;
        bool expect;
    };
    vector<Case> cases = {
        {"ab", "eidbaooo", true},   // 窗口 "ba"
        {"ab", "eidboaoo", false},  // 长度对但字符不匹配
        {"a", "a", true},           // 单字符
        {"abc", "ab", false},       // s1 更长，边界
        {"adc", "dcda", true},      // 排列跨越初始窗口起点
        {"hello", "ooolleoooleh", false},
    };

    int failed = 0;
    for (const auto& c : cases) {
        bool got = s.checkInclusion(c.s1, c.s2);
        bool ok = (got == c.expect);
        if (!ok) failed++;
        cout << (ok ? "PASS" : "FAIL") << "  s1=\"" << c.s1 << "\"  s2=\"" << c.s2
             << "\"  got=" << got << "  expect=" << c.expect << endl;
    }
    cout << (failed == 0 ? "all checks passed" : "FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
