package leetcode;

/**
 * @author : lishuming
 */
public class MissingNumber268 {
    public int missingNumber(int[] nums) {
        int result = nums.length;

        for (int i = 0; i < nums.length; i++) {
            result += (i - nums[i]);
        }

        return result;
    }

    public int todo(int[] nums) {
        boolean hasZero = false;
        for (int i = 0; i < nums.length; i++) {
            int t = Math.abs(nums[i]);
            if (t == 0) {
                hasZero = true;
            }

            if (t < nums.length) {
                nums[t] = -nums[t];
            }
        }

        int i = 0;
        for (; i < nums.length; i++) {
            if (nums[i] > 0) {
                return i;
            }
        }

        return i;
    }

    public static void main(String[] args) {
        int[] test = new int[] {3, 0, 1};
        //int[] test = new int[]{9,6,4,2,3,5,7,0,1};
        //int[] test = new int[]{0, 1};
        //int[] test = new int[]{2, 0};
        int r = new MissingNumber268().missingNumber(test);
        System.out.println(r);
    }
}
