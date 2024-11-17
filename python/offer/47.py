

"""
Descprtion:https://doocs.github.io/leetcode/lcof/47/#_1
"""
class Solution:
    def maxValue(self, grid: list[list[int]]) -> int:
        m, n = len(grid), len(grid[0])
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1]) + grid[i - 1][j - 1]
        return dp[m][n]

if __name__ == '__main__':
    s = Solution()
    print(s.maxValue([[1, 3, 1], [1, 5, 1], [4, 2, 1]]))  # 12
    print(s.maxValue([[1, 2, 5], [3, 2, 1]]))  # 9
    print(s.maxValue([[1, 2, 3], [4, 5, 6]]))  # 12
    print(s.maxValue([[1, 2, 3]]))  # 6
    print(s.maxValue([[1], [2], [3]]))  # 6
    print(s.maxValue([[1]]))  # 1
    print(s.maxValue([[1, 2, 3, 4, 5]]))  # 15
    print(s.maxValue([[1], [2], [3], [4], [5]]))  # 15