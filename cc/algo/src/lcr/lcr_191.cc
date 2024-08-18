#include "../include/fwd.h"

class Solution {
public:
    vector<int> statisticalResult(vector<int>& arrayA) {
        int n = arrayA.size();
        if (n == 0) return {};

        vector<int> prefix_mul(n, 1);
        prefix_mul[0] = arrayA[0];
        for (int i = 1; i < n; i++) {
            prefix_mul[i] = prefix_mul[i - 1] * arrayA[i];
        }
        vector<int> suffix_mul(n, 1);
        suffix_mul[n - 1] = arrayA[n - 1];
        for (int i = n - 2; i >= 0; i--) {
            suffix_mul[i] = suffix_mul[i + 1] * arrayA[i];
        }
        vector<int> result(n);
        result[0] = suffix_mul[1];
        result[n - 1] = prefix_mul[n - 2];
        for (int i = 1; i < n - 1; i++) {
            result[i] = prefix_mul[i - 1] * suffix_mul[i + 1];
        }
        return result;
    }
};

int main() {
    Solution solution;
    vector<int> arrayA = {1, 2, 3, 4, 5};
    vector<int> result = solution.statisticalResult(arrayA);
    for (int i = 0; i < result.size(); i++) {
        cout << result[i] << " ";
    }
    cout << endl;
    return 0;
}