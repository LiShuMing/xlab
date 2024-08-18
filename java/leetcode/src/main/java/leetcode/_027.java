package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _027 {
  public int removeElement(int[] nums, int val) {
    int i = 0;
    for (int n: nums) {
      if (n != val) {
        nums[i++] = n;
      }
    }
    return i;
  }
  static public void main(String[] args) {
    int[] nums = {3, 2, 2, 3};
    System.out.println(new _027().removeElement(nums, 3));
    for (int n: nums) {
      System.out.println(n);
    }
  }
}
