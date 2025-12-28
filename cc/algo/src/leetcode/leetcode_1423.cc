#include "../include/fwd.h"

class Solution {
public:
    int maxScore(vector<int>& cardPoints, int k) {
        int n = cardPoints.size();
        int sum = 0;
        int w = n - k;

        // calculate the sum of the first w cards
        for (int i = 0; i < w; i++) {
            sum += cardPoints[i];
        }
        int ans = sum;
        for (int i = w; i < n; i++) {
            sum += cardPoints[i] - cardPoints[i - w];
            ans = min(ans, sum);
        }
        return accumulate(cardPoints.begin(), cardPoints.end(), 0) - ans;
    }
};

int main() {
    Solution solution;
    vector<int> cardPoints = {1, 2, 3, 4, 5, 6, 1};
    int k = 3;
    cout << solution.maxScore(cardPoints, k) << endl;
    return 0;
}