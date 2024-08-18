
import bisect

from bisect import bisect_left
from typing import List

class Solution:
    def lengthOfLIS(self, nums: List[int]) -> int:
        g = []
        for x in nums:
            print("g:" + str(g) + ", x:" + str(x))
            j = bisect_left(g, x)
            if j == len(g):  # >=x 的 g[j] 不存在
                g.append(x)
            else:
                g[j] = x
        return len(g)

if __name__ == "__main__":
    s = Solution()
    # print(s.lengthOfLIS([10, 9, 2, 5, 3, 7, 101, 18]))  # 4
    print(s.lengthOfLIS([1, 2, 3, 10, 9, 2, 5, 3, 7, 101, 18]))  # 4
    # print(s.lengthOfLIS([0, 1, 0, 3, 2, 3]))  # 4
    # print(s.lengthOfLIS([7, 7, 7, 7, 7, 7, 7]))  # 1
    # print(s.lengthOfLIS([7, 7, 7, 7, 7, 7, 7, 7]))  # 1
    # print(s.lengthOfLIS([7, 7, 7, 7, 7, 7, 7, 7, 7]))  # 1
    # print(s.lengthOfLIS([7, 7, 7, 7, 7, 7, 7, 7, 7, 7]))  # 1
    # print(s.lengthOfLIS([7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]))  # 1