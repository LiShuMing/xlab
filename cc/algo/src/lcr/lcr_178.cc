#include "../include/fwd.h"

class Solution {
public:
    int trainingPlan(vector<int>& actions) {
        int counts[32] = {0}; // C++ 初始化数组需要写明初始值 0
        for (int action : actions) {
            for (int i = 0; i < 32; i++) {
                counts[i] += action & 1; // 更新第 i 位 1 的个数之和
                action >>= 1;            // 第 i 位 --> 第 i 位
            }
        }
        int res = 0, m = 3;
        for (int i = 31; i >= 0; i--) {
            res <<= 1;
            res |= counts[i] % m; // 恢复第 i 位
        }
        return res;
    }
};

int main() {
    Solution solution;
    cout << solution.solution(1) << endl;
    return 0;
}