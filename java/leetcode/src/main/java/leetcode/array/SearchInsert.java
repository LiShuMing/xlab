package leetcode.array;

/**
 * @author : lishuming
 */
public class SearchInsert {
    public static int solution(int[] nums, int target) {
        int l = 0, mid = 0, len = nums.length, r = len;

        if (target > nums[len - 1]) {
            return len;
        }
        if (target < nums[0]) {
            return 0;
        }
        while (l < r) {
            mid = (l + r) / 2;
            if (nums[mid] == target) {
                return mid;
            } else if (nums[mid] < target) {
                l = mid;
            } else {
                r = mid;
            }

            if (r - l == 1) {
                return r;
            }
        }

        return r;
    }
}
