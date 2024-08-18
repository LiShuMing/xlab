package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _080 {
    public int removeDuplicates(int[] nums) {
        int i = 0, j = 0, v = 0;
        for (int n: nums) {
            if (i == 0)  {
                nums[i++] = n;
                v = n;
                j++;
                continue;
            }

            if (n != v) {
                j = 1;
                nums[i++] = n;
                v = n;
                continue;
            }

            if (j++ < 2) {
                nums[i++] = n;
            }
        }
        return i;
    }
    static public void main(String[] args) {
        int[] nums = {0,0,1,1,1,1,2,3,3};
        int r = new _080().removeDuplicates(nums);
        System.out.println("len:" + r);
        for (int i = 0; i < r; i++) {
            System.out.println(nums[i]);
        }
    }
}
