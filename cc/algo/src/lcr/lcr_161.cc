#include "../include/fwd.h"

class Solution {
public:
    int maxSales(vector<int>& sales) {
        // int n = sales.size();
        // vector<int> dp(n, 0);
        // dp[0] = sales[0];
        // dp[1] = max(sales[0], sales[1]);
        // for (int i = 2; i < n; i++) {
        //     dp[i] = max(dp[i - 1], dp[i - 2] + sales[i]);
        // }
        // return dp[n - 1];


        // int n = sales.size();
        // if (n == 0) return 0;
        // int maxSum = sales[0];
        // int currentSum = sales[0];
        // for (int i = 1; i < n; i++) {
        //     currentSum = max(sales[i], currentSum + sales[i]);
        //     maxSum = max(maxSum, currentSum);
        // }
        // return maxSum;

        int n = sales.size();
        if (n == 0) return 0;
        int t = sales[0];
        int ans = t;
        for (int i = 1; i < n; i++) {
            t += sales[i];
            if (t < sales[i]) {
                t = sales[i];
            }
            ans = max(ans, t);
        }
        return ans;
    }
};

int main() {
    Solution solution;
    int arr[] = {-2,1,-3,4,-1,2,1,-5,4};
    vector<int> sales(arr, arr + sizeof(arr) / sizeof(arr[0]));
    cout << solution.maxSales(sales) << endl;
    return 0;
}