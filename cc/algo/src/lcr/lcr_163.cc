#include "../include/fwd.h"

class Solution {
public:
    int findKthNumber(int k) {
        // binary search to find the number
        int left = 1, right = 9;
        while (left < right) {
            int mid = left + (right - left) / 2;
            if (totalNumbers(mid) < k) {
                left = mid + 1;
            } else {
                right = mid;
            }
        }

        // compute the kth number
        int n = left;
        int prev = totalNumbers(n - 1);
        int index = k - prev - 1;

        int start = (int) pow(10, n - 1);
        int num = start + index / n;
        string s = to_string(num);
        return s[index % n] - '0';
    }

    // return the total number of digits in the numbers from 1 to n
    int totalNumbers(int n) {
        int ans = 0;
        int cur_len = 1, cur_count = 9;
        while (cur_len <= n) {
            ans += cur_count * cur_len;
            cur_len++;
            cur_count *= 10;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.findKthNumber(5) << endl;
    return 0;
}