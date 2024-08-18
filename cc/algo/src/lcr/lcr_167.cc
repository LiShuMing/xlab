#include "../include/fwd.h"

class Solution {
public:
    int dismantlingAction(string arr) {
        if (arr.empty()) return 0;
        int n = arr.size();
        int ans = 0;
        int l = 0;
        unordered_set<char> st;
        for (int i = 0; i < n; i++) {
            if (st.find(arr[i]) != st.end()) {
                // Found duplicate, remove characters from left until we remove the duplicate
                while (l < i && arr[l] != arr[i]) {
                    st.erase(arr[l]);
                    l++;
                }
                st.erase(arr[l]);
                l++;
            }
            st.insert(arr[i]);
            ans = max(ans, i - l + 1);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.dismantlingAction("dbascDdad") << endl;
    cout << solution.dismantlingAction("zzzxxxccc") << endl;
    return 0;
}