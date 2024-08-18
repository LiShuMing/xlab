#include "../include/fwd.h"

class Solution {
public:
    long long maxPower(vector<int>& stations, int r, int k) {}
};

int main() {
    Solution solution;
    vector<int> stations = {1, 2, 4, 5};
    int r = 2, k = 6;
    cout << "stations: ";
    printVector(stations);
    cout << "r: " << r << ", k: " << k << ", ans: " << solution.maxPower(stations, r, k) << endl;
    return 0;
}