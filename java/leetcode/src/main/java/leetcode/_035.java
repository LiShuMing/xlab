package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/09
 */
public class _035 {
    public int searchInsert(int[] nums, int target) {
        if (nums == null) return 0;

        int len = nums.length, i = 0;
        for (; i < len; i++) {
            if (target <= nums[i] ) {
                return i;
            }
        }
        return i;
    }
}
