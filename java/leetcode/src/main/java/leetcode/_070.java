package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/24
 */
public class _070 {
    public int climbStairs(int n) {
        return fib(n);
    }

    private int fib(int n) {
        if (n == 1) {
            return 1;
        }
        if (n == 2) {
            return 2;
        }
        return fib(n - 1) + fib(n - 2);
    }

    public int climbStairs2(int n) {
        int[] dp = new int[n + 1];
        dp[0] = 1;
        dp[1] = 1;

        for (int i = 2; i <= n; i++) {
            dp[i] = dp[i - 1] + dp[i - 2];
        }
        return dp[n];
    }

    public static void main(String[] args) {
        int r = new _070().climbStairs2(45);
        System.out.println(r);
    }
}
