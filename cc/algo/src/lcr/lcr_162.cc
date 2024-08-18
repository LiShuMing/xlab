#include "../include/fwd.h"

class Solution {
public:
    int digitOneInNumber(int num) {
        string s = to_string(num);
        int n = s.size();
        // prefix sum
        vector<int> ps(n);
        // suffix sum
        vector<int> ns(n);

        ss[0] = atoi(s.substr(1).c_str());
        for (int i = 1; i < s.size() - 1; i++) {
            ps[i] = atoi(s.substr(0, i).c_str());
            ns[i] = atoi(s.substr(i + 1).c_str());
        }
        ps[n - 1] = atoi(s.substr(0, n - 1).c_str());

        int ans = 0;
        for (int i = 0; i < s.size(); i++) {
            int l = n - i - 1;
            ans += ps[i] * pow(10, l);
            if (s[i] == '1') {
                ans += ns[i] + 1;
            } else if (s[i] > '0') {
                ans += pow(10, l);
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.digitOneInNumber(1) << endl;
    cout << solution.digitOneInNumber(10) << endl;
    cout << solution.digitOneInNumber(100) << endl;
    cout << solution.digitOneInNumber(1000) << endl;
    cout << solution.digitOneInNumber(10000) << endl;
    cout << solution.digitOneInNumber(100000) << endl;
    cout << solution.digitOneInNumber(1000000) << endl;
    cout << solution.digitOneInNumber(10000000) << endl;
    cout << solution.digitOneInNumber(100000000) << endl;
    cout << solution.digitOneInNumber(1000000000) << endl;
    return 0;
}