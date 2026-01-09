#include "../include/fwd.h"
class Solution {
public:
    int sumFourDivisors(vector<int>& nums) {
        int ans = 0;
        for (int i = 0; i < nums.size(); i++) {
            int num = nums[i];
            int cnt = 0;
            int sum = 0;
            for (int j = 1; j * j <= num; j++) {
                if (num % j == 0) {
                    cnt++;
                    sum += j;
                    if (j != num / j) {
                        cnt++;
                        sum += num / j;
                    }
                    if (cnt > 4) {
                        break;
                    }
                }
            }
            if (cnt == 4) {
                ans += sum;
            }
        }
        return ans;
    }
};

int main() {
    Solution solution;
    int arr[] = {21, 4, 7};
    vector<int> nums(arr, arr + 3);
    cout << solution.sumFourDivisors(nums) << endl;
    return 0;
}
