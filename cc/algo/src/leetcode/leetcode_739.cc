#include "../include/fwd.h"

class Solution {
public:
    vector<int> dailyTemperatures(vector<int>& temperatures) {
        // 单调栈
        stack<int> s;
        vector<int> res(temperatures.size(), 0);
        for (int i = 0; i < temperatures.size(); ++i) {
            while (!s.empty() && temperatures[i] > temperatures[s.top()]) {
                res[s.top()] = i - s.top();
                s.pop();
            }
            s.push(i);
        }
        return res;
    }
};
