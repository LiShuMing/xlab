#include "../include/fwd.h"

class Solution {
public:
    int reversePairs(vector<int>& record) {
        // use a merge sort to count the reverse pairs
        int n = record.size();
        vector<int> temp(n);
        return mergeSort(record, temp, 0, n - 1);
    }
    int mergeSort(vector<int>& record, vector<int>& temp, int left, int right) {
        if (left >= right) return 0;
        int mid = (left + right) / 2;
        int count = mergeSort(record, temp, left, mid) + mergeSort(record, temp, mid + 1, right);
        int i = left, j = mid + 1, k = left;
        while (i <= mid && j <= right) {
            if (record[i] > record[j]) {
                count += mid - i + 1;
                temp[k++] = record[j++];
            } else {
                temp[k++] = record[i++];
            }
        }
        while (i <= mid) {
            temp[k++] = record[i++];
        }
        while (j <= right) {
            temp[k++] = record[j++];
        }
        for (int i = left; i <= right; i++) {
            record[i] = temp[i];
        }
        return count;
    }
};

int main() {
    Solution solution;
    cout << solution.reversePairs({7, 5, 6, 4}) << endl;
    return 0;
}