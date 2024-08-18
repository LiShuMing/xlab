#include "../include/fwd.h"

class Solution {
public:
    int inventoryManagement(vector<int>& stock) {
        if (stock.empty()) {
            return -1;
        }
        // use moore voting algorithm to find the majority element
        int candidate = stock[0];
        int count = 1;
        for (int i = 1; i < stock.size(); i++) {
            if (stock[i] == candidate) {
                count++;
            } else {
                count--;
            }
            if (count == 0) {
                candidate = stock[i];
                count = 1;
            }
        }
        return candidate;
    }
};

int main() {
    Solution solution;
    vector<int> stock = {1, 2, 3, 4, 5, 1, 1, 1, 1, 1};
        cout << solution.inventoryManagement(stock) << endl;
        return 0;
    }
};