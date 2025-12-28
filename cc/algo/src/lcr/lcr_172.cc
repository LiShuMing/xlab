#include "../include/fwd.h"

class Solution {
public:
    int countTarget(vector<int>& scores, int target) {
        // auto iter = lower_bound(scores.begin(), scores.end(), target);
        // if (iter == scores.end()) {
        //     return 0;
        // }
        // int count = 0;
        // while (iter != scores.end() && *iter == target) {
        //     iter++;
        //     count++;
        // }
        // return count;
        int lower_bound = binarySearch(scores, target, true);
        int upper_bound = binarySearch(scores, target, false);
        return upper_bound - lower_bound + 1;
    }

    int binarySearch(vector<int>& scores, int target, bool is_lower_bound) {
        int left = 0, right = scores.size() - 1;
        while (left <= right) {
            int mid = left + (right - left) / 2;
            if (scores[mid] == target) {
                if (is_lower_bound) {
                    right = mid - 1;
                } else {
                    left = mid + 1;
                }
            } else if (scores[mid] < target) {
                left = mid + 1;
            } else {
                right = mid - 1;
            }
        }
        return is_lower_bound ? left : right;
    }
};

int main() {
    Solution solution;
    vector<int> scores = {1, 2, 3, 4, 5};
    int target = 3;
    cout << solution.countTarget(scores, target) << endl;
    return 0;
}