#include "../include/fwd.h"
class Solution {
public:
    int takeAttendance(vector<int>& records) {
        int n = records.size();
        for (int i = 0; i < n; i++) {
            if (records[i] != i) {
                return i;
            }
        }
        return n;
    }
};

int main() {
    Solution solution;
    vector<int> records = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    cout << solution.takeAttendance(records) << endl;
    return 0;
}