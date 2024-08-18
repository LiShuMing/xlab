package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _026 {
    public int removeDuplicates(int[] nums) {
        int i = 0, v = 0;
        for (int n : nums) {
            if (i == 0 || n != v) {
                v = n;
                nums[i++] = n;
            }
        }
        return i;
    }
}
