#include "../include/fwd.h"

class Solution {
public:
    bool verifyTreeOrder(vector<int>& postorder) { 
        if (postorder.empty()) return true;
        return dfs(postorder, 0, postorder.size() - 1); 
    }

    bool dfs(vector<int>& postorder, int start, int end) {
        if (start >= end) return true;
        int root = postorder[end];
        int i = start;
        while (i < end && postorder[i] < root) i++;
        int j = i;
        while (j < end && postorder[j] > root) j++;
        return j == end && dfs(postorder, start, i - 1) && dfs(postorder, i, end - 1);
    }
};

int main() {
    Solution solution;
    // vector<int> postorder = {1, 3, 2, 6, 5, 7, 4};
    int arr[] = {4, 9, 6, 5, 8};
    vector<int> postorder(arr, arr + sizeof(arr) / sizeof(arr[0]));
    cout << solution.verifyTreeOrder(postorder) << endl;
    return 0;
}