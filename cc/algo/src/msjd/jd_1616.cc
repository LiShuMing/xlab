#include "../include/fwd.h"
class Solution {
    public:
        vector<int> subSort(vector<int>& array) {
            int n = array.size();
            int max_val = INT_MIN;
            int min_val = INT_MAX;
            int left = -1;
            int right = -1;
            for (int i = 0; i < n; i++) {
                if (array[i] < max_val) {
                    right = i;
                } else {
                    max_val = max(max_val, array[i]);
                }

                if (array[n - i - 1] > min_val) {
                    left = n - i - 1;
                } else {
                    min_val = min(min_val, array[n - i - 1]);
                }
            }
            return {left, right};
        }
    };