#include "../include/fwd.h"
#include <string>

/**
 * LeetCode 2217: Find Palindrome With Fixed Length
 * 
 * Given an integer array `queries` and an integer `intLength`, return an array
 * `ans` where `ans[i]` is the `queries[i]`-th palindrome number of length
 * `intLength`. If it doesn't exist, return -1.
 * 
 * Approach:
 * - Palindromes are determined by their left half
 * - For even length: palindrome = left * 10^len(left) + reverse(left)
 * - For odd length: palindrome = left * 10^(len(left)-1) + reverse(left without last digit)
 * - Range check: max palindromes = 9 * 10^(half - 1)
 */
class Solution {
public:
    vector<long long> kthPalindrome(vector<int>& queries, int intLength) {
        vector<long long> ans(queries.size(), -1);
        
        for (size_t i = 0; i < queries.size(); i++) {
            ans[i] = getKthPalindrome(queries[i], intLength);
        }
        
        return ans;
    }
    
private:
    long long getKthPalindrome(int k, int len) {
        // Calculate the number of palindromes and starting point
        int halfLen = (len + 1) / 2;
        long long start = 1;
        for (int i = 1; i < halfLen; i++) {
            start *= 10;
        }
        long long maxCount = 9 * start;
        
        // Check if k is out of range
        if (k > maxCount || k < 1) {
            return -1;
        }
        
        // Calculate the left half
        long long left = start + k - 1;
        
        // Build the full palindrome
        long long palindrome = left;
        long long right = reverseNumber(left);
        
        if (len % 2 == 0) {
            // Even length: mirror all digits
            while (right > 0) {
                palindrome = palindrome * 10 + (right % 10);
                right /= 10;
            }
        } else {
            // Odd length: skip the middle digit (last digit of left)
            right = reverseNumber(left / 10);
            while (right > 0) {
                palindrome = palindrome * 10 + (right % 10);
                right /= 10;
            }
        }
        
        return palindrome;
    }
    
    long long reverseNumber(long long n) {
        long long rev = 0;
        while (n > 0) {
            rev = rev * 10 + (n % 10);
            n /= 10;
        }
        return rev;
    }
};
