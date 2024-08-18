#include "../include/fwd.h"

class Solution {
public:
    bool validateBookSequences(vector<int>& putIn, vector<int>& takeOut) {
        stack<int> st;
        int i = 0;
        int j = 0;
        while (j < takeOut.size()) {
            if (!st.empty() && st.top() == takeOut[j]) {
                st.pop();
                j++;
            } else if (i < putIn.size()) {
                st.push(putIn[i]);
                i++;
            } else {
                return false;
            }
        }
        return true;
    }
};
int main() {
    Solution solution;
    int arr1[] = {1, 2, 3, 4, 5};
    vector<int> putIn(arr1, arr1 + sizeof(arr1) / sizeof(arr1[0]));
    int arr2[] = {4, 5, 3, 2, 1};
    vector<int> takeOut(arr2, arr2 + sizeof(arr2) / sizeof(arr2[0]));
    cout << solution.validateBookSequences(putIn, takeOut) << endl;
    return 0;
}