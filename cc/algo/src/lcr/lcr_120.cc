#include "../include/fwd.h"

class Solution {
public:
    int findRepeatDocument(vector<int>& documents) {
        for (int i = 0; i < documents.size(); i++) {
            while (documents[i] != i) {
                if (documents[i] == documents[documents[i]]) {
                    return documents[i];
                }
                swap(documents[i], documents[documents[i]]);
            }
        }
        return -1;
    }
    // int findRepeatDocument(vector<int>& documents) {
    //     unordered_map<int, int> freq;
    //     for (int doc : documents) {
    //         freq[doc]++;
    //         if (freq[doc] > 1) {
    //             return doc;
    //         }
    //     }
    //     return -1;
    // }
};

int main() {
    Solution solution;
    vector<int> documents = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    int result = solution.findRepeatDocument(documents);
    cout << result << endl;
    return 0;
}