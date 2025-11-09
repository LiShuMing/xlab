#include "../include/fwd.h"

class Solution {
public:
    int minimumOneBitOperations(int n) {
        if (n == 0) return 0;
        int k = 31 - __builtin_clz(n);
        // return (1 << k) - 1 - minimumOneBitOperations(n - (1 << (k - 1)));
        return (1 << (k + 1)) - 1 - minimumOneBitOperations(n - (1 << k));
    }

    int minimumOneBitOperations2(int n) {
        int ans = 0;
        while (n > 0) {
            ans ^= n;
            n >>= 1;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    for (int n = 0; n < 16; n++) {  
        int ans = solution.minimumOneBitOperations(n);
        int ans2 = solution.minimumOneBitOperations2(n);
        cout << "n: " << n << ", ans: " << ans << ", ans2: " << ans2 << endl;
        assert((ans == ans2) && "ans != ans2");
    }
    return 0;
}