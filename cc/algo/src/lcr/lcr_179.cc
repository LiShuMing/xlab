#include "../include/fwd.h"
class Solution {
public:
    vector<int> twoSum(vector<int>& price, int target) {
        int n = price.size();
        int left = 0, right = n - 1;
        while (left < right) {
            if (price[left] + price[right] == target) {
                return {price[left], price[right]};
            } else if (price[left] + price[right] < target) {
                left++;
            } else {
                right--;
            }
        }
        return {-1, -1};
    }
};

int main() {
    Solution solution;
    vector<int> price = {1, 2, 3, 4, 5};
    int target = 3;
    vector<int> result = solution.twoSum(price, target);
    cout << result[0] << " " << result[1] << endl;
    return 0;
}