#include "../include/fwd.h"

class Solution {
public:
    vector<vector<int>> fileCombination(int target) {
        vector<vector<int>> result;
        int l = target / 2;
        for (int i = 1; i <= l; i++) {
            int sum = 0;
            for (int j = i; j < target; j++) {
                sum += j;
                if (sum == target) {
                    vector<int> temp;
                    for (int k = i; k <= j; k++) {
                        temp.push_back(k);
                    }
                    result.push_back(temp);
                    break;
                } else if (sum > target) {
                    break;
                }
            }
        }
        return result;
    }
};
int main() {
    Solution solution;
    vector<vector<int>> result = solution.fileCombination(10);
    for (int i = 0; i < result.size(); i++) {
        for (int j = 0; j < result[i].size(); j++) {
            cout << result[i][j] << " ";
        }
        cout << endl;
    }
    return 0;
}