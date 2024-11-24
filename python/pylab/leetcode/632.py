from typing import List

import heapq
'''
You have k lists of sorted integers in non-decreasing order. Find the smallest range that includes at least one number from each of the k lists.

We define the range [a, b] is smaller than range [c, d] if b - a < d - c or a < c if b - a == d - c.

Example 1:
Input: nums = [[4,10,15,24,26],[0,9,12,20],[5,18,22,30]]
Output: [20,24]
Explanation: 
List 1: [4, 10, 15, 24,26], 24 is in range [20,24].
List 2: [0, 9, 12, 20], 20 is in range [20,24].
List 3: [5, 18, 22, 30], 22 is in range [20,24].
Example 2:

Input: nums = [[1,2,3],[1,2,3],[1,2,3]]
Output: [1,1]
'''

# [4,10,15,24,26]
# [0,9,12,20]
# [5,18,22,30]

class Solution:
    def smallestRange(self, nums: List[List[int]]) -> List[int]:
        h = [(row[0], i, 0) for i, row in enumerate(nums)]
        heapq.heapify(h)
        ans_l = h[0][0]
        ans_r = r = max(row[0] for row in nums)
        def cur_idx():
            return h[0][2]
        def cur_arr():
            return h[0][1]
        
        while cur_idx() < len(nums[cur_arr()]):
            val, arr, idx = heapq.heappop(h)
            if r - val < ans_r - ans_l:
                ans_l, ans_r = val, r
            if idx + 1 == len(nums[arr]):
                break
            r = max(r, nums[arr][idx + 1])
            heapq.heappush(h, (nums[arr][idx + 1], arr, idx + 1))
        return [ans_l, ans_r]

if __name__ == '__main__':
    s = Solution()
    print(s.smallestRange([[4,10,15,24,26],[0,9,12,20],[5,18,22,30]])) # [20,24]
    print(s.smallestRange([[1,2,3],[1,2,3],[1,2,3]])) # [1,1]