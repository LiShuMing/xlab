package leetcode;

import java.util.ArrayList;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2020/04/26
 */
public class _053 {
    public int maxSubArray(int[] nums) {
        int r = nums[0];
        int sum = 0;
        for (int n: nums) {
            if (sum > 0) {
                sum += n;
            } else {
                sum = n;
            }
            r = Math.max(r, sum);
        }
        return r;
    }

    public static void main(String[] args) {
        int[] nums = {-2,1,-3,4,-1,2,1,-5,4};
        int ret = new _053().maxSubArray(nums);
        System.out.println("ret:" + ret);
    }
}
