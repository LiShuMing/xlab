package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _485 {
    public int findMaxConsecutiveOnes(int[] nums) {
        int i = 0, max = 0;
        for (int n: nums) {
            if (n == 1) {
                i++;
            } else {
                if (i > max) {
                    max = i;
                }
                i = 0;
            }
        }
        if (i > max) {
            max = i;
        }
        return max;
    }

    static public void main(String[] args) {
        int[] nums = {0, 0, 1, 1, 1, 1, 2, 3, 3};
        int r = new _485().findMaxConsecutiveOnes(nums);
        System.out.println("R:" + r);
    }
}
