package leetcode.array;

/**
 * @author : lishuming
 */
public class RemoveElement {
    public static int solution(int[] nums, int val) {
        int len = nums.length;
        if (len < 1) {
            return len;
        }

        int i = 0, j = 0;
        while (i < len) {
            if (val != nums[i]) {
                if (j < i) {
                    nums[j] = nums[i];
                }
                j++;
            }
            i++;
        }

        return j;
    }
}
