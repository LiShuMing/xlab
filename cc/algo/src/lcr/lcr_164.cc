#include "../include/fwd.h"

class Solution {
public:
    string intToString(int num) {
        if (num == 0) return "0";
        string result = "";
        int temp = num;
        if (temp < 0) {
            result += "-";
            temp = -temp;
        }
        while (temp > 0) {
            result = char('0' + temp % 10) + result;
            temp /= 10;
        }
        return result;
    }
    
    string crackPassword(vector<int>& password) {
        if (password.empty()) return "";
        
        // Convert all numbers to strings
        vector<string> strs;
        for (int i = 0; i < password.size(); i++) {
            strs.push_back(intToString(password[i]));
        }
        
        // Sort with custom comparator: a+b < b+a (lexicographically)
        for (int i = 0; i < strs.size(); i++) {
            for (int j = i + 1; j < strs.size(); j++) {
                string ab = strs[i] + strs[j];
                string ba = strs[j] + strs[i];
                if (ab > ba) {
                    string temp = strs[i];
                    strs[i] = strs[j];
                    strs[j] = temp;
        }
    }
        }
        
        // Concatenate all strings
        string result = "";
        for (int i = 0; i < strs.size(); i++) {
            result += strs[i];
        }
        return result;
    }
};

int main() {
    Solution solution;
    int arr[] = {15, 8, 9};
    vector<int> password(arr, arr + sizeof(arr) / sizeof(arr[0]));
    cout << solution.crackPassword(password) << endl;
    return 0;
}