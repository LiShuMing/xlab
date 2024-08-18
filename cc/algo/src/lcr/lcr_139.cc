#include "../include/fwd.h"

class Solution {
    public:
        vector<int> trainingPlan(vector<int>& actions) {
            int n = actions.size();
            int l = 0, r = n - 1;
            while (l < r) {
                while (l < r && actions[l] % 2 == 1) {
                    l++;
                } 
                while (l < r && actions[r] % 2 == 0) {
                    r--;
                }
                if (l < r) {
                    swap(actions[l], actions[r]);
                    l++;
                }
            }
            return actions;
        }
    };

int main() {
    Solution solution;
    vector<int> actions = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    vector<int> result = solution.trainingPlan(actions);
    for (int i = 0; i < result.size(); i++) {
        cout << result[i] << " ";
    }
    cout << endl;
    return 0;
}