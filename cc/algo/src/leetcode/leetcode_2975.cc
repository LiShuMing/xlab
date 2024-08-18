#include "../include/fwd.h"

const int MOD = 1e9 + 7;

class Solution {
private:
    unordered_set<int> getEdges(vector<int>& fences, int m) {
        unordered_set<int> st;
        fences.push_back(1);
        fences.push_back(m);
        sort(fences.begin(), fences.end());
        for (int i = 0; i < fences.size(); i++) {
            for (int j = i + 1; j < fences.size(); j++) {
                st.insert(fences[j] - fences[i]);
            }
        }
        return st;
    }
public:
    int maximizeSquareArea(int m, int n, vector<int>& hFences, vector<int>& vFences) {
        unordered_set<int> hEdges = getEdges(hFences, m);
        unordered_set<int> vEdges = getEdges(vFences, n);
        int ans = 0;
        for (int hEdge : hEdges) {
            if (vEdges.count(hEdge)) {
                ans = max(ans, hEdge);
            }
        }
        if (ans == 0) {
            return -1;
        }
        return ans * ans % MOD;
    }
};

int main() {
    Solution solution;
    vector<int> hFences = {1, 3, 5};
    vector<int> vFences = {2, 4, 6};
    cout << solution.maximizeSquareArea(5, 5, hFences, vFences) << endl;
    return 0;
}