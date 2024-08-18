package leetcode;

/**
 * @author : lishuming
 */
public class SingleNumber136 {
    public int singleNumber(int[] nums) {
        int ret = 0;

        for (int i = 0; i < nums.length; i++) {
            ret ^= nums[i];
        }

        return ret;
    }

    public static void main(String[] args) {
        int[] t = new int[] {2, 2, 1};
        int r = new SingleNumber136().singleNumber(t);
        System.out.println(r);
    }
}
