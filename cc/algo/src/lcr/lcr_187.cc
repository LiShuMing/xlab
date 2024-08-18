#include "../include/fwd.h"

class Solution {
public:
    int iceBreakingGame(int num, int target) {
        if (num == 1) {
            return 0;
        }
        int ans = 0;
        for (int i = 2; i != num + 1; i++) {
            ans = (target + ans) % i;
        }
        return ans;
    }
};

int main() {
    Solution solution;
    cout << solution.iceBreakingGame(5, 3) << endl;
    return 0;
}