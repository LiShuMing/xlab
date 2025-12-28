#include "../include/fwd.h"
class Solution {
public:
    int inventoryManagement(vector<int>& stock) {
        int n = stock.size();
        int l = 0; int r = n - 1;
        while (l < r) {
            int mid = l + (r - l) / 2;
            // If stock[mid] < stock[r], the right side is sorted, so the minimum is on the left (including mid) → r = mid
            // Otherwise, the left side is sorted, so the minimum is on the right (excluding mid) → l = mid + 1
            if (stock[mid] < stock[r]) {
                r = mid;
            } else {
                l = mid + 1;
            }
        }
        return stock[l];
    }
};
int main() {
    Solution solution;
    int arr[] = {5, 6, 7, 8, 9, 10, 1, 2, 3, 4};
    vector<int> stock(arr, arr + sizeof(arr) / sizeof(arr[0]));
    cout << solution.inventoryManagement(stock) << endl;
    return 0;
}