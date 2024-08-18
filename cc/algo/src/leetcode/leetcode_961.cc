#include "../include/fwd.h"
class Solution {
public:
    int repeatedNTimes(vector<int>& nums) {
        unordered_map<int, int> freq;
        for (int num : nums) {
            freq[num]++;
            if (freq[num] > 1) {
                return num;
            }
        }
        return -1;
    }
};
int main() {
    Solution solution;
    cout << solution.repeatedNTimes(nums) << endl;
    return 0;
}