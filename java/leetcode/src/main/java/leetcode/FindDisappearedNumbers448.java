package leetcode;

import java.util.ArrayList;
import java.util.List;

/**
 * @author : lishuming
 */
public class FindDisappearedNumbers448 {
    public List<Integer> findDisappearedNumbers(int[] nums) {
        List<Integer> res = new ArrayList<>();

        //TODO: can not run??
        // sort nums
        quickSort(nums, 0, nums.length - 1);
        return null;
    }

    public List<Integer> solution(int[] nums) {
        List<Integer> res = new ArrayList<>();

        for (int i = 0; i < nums.length; i++) {
            int t = Math.abs(nums[i]);
            nums[t - 1] = nums[t - 1] > 0 ? -nums[t - 1] : nums[t - 1];
        }

        for (int i = 0; i < nums.length; i++) {
            if (nums[i] > 0) {
                res.add(i + 1);
            }
        }

        return res;
    }

    protected void quickSort(int[] nums, int start, int end) {
        if (start > end) {
            return;
        }

        int i = start;
        int j = end;

        int pivot = nums[start];
        while (i < j) {
            while (i < j && nums[j] >= pivot) {
                j--;
            }
            if (i < j) {
                nums[i++] = nums[j];
            }

            while (i < j && nums[i] <= pivot) {
                i++;
            }
            if (i < j) {
                nums[j--] = nums[i];
            }
        }
        nums[i] = pivot;

        if (i > start) {
            quickSort(nums, start, i - 1);
        }

        if (i < end) {
            quickSort(nums, i + 1, end);
        }
    }

    public static void main(String[] args) {
        //int[] nums = new int[]{23, 10, 12, 2, 21, 100};
        /**
         int[] nums = new int[]{4, 3, 2, 7, 8, 2, 3, 1};
         new FindDisappearedNumbers448().quickSort(nums, 0, nums.length - 1);
         for (int i = 0; i < nums.length; i++) {
         System.out.println(nums[i]);
         }*/

        int[] test = new int[] {4, 3, 2, 7, 8, 2, 3, 1};
        //int[] test = new int[]{1,1};
        //List<Integer> res = new FindDisappearedNumbers448().findDisappearedNumbers(test);
        List<Integer> res = new FindDisappearedNumbers448().solution(test);
        for (Integer i : res) {
            System.out.println(i);
        }
    }
}
