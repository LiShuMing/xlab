package leetcode;

/**
 * @author : lishuming
 */
public class FirstMissingPositive41 {
    public int firstMissingPositive(int[] nums) {
        quickSort(nums, 0, nums.length - 1);

        int j = 1;
        for (int i = 0; i < nums.length; i++) {
            //System.out.println(i);
            System.out.println(nums[i]);
            if (nums[i] < j) {
                continue;
            } else if (nums[i] == j) {
                j++;
            } else {
                return j;
            }
        }

        return j;
    }

    public void quickSort(int[] nums, int start, int end) {
        if (start >= end) {
            return;
        }

        int i = start;
        int j = end;
        int pivot = nums[start];

        while (i < j) {
            while (i < j && nums[j] > pivot) {
                j--;
            }
            if (i < j) {
                nums[i++] = nums[j];
            }

            while (i < j && nums[i] < pivot) {
                i++;
            }
            if (i < j) {
                nums[j--] = nums[i];
            }
        }
        nums[i] = pivot;

        quickSort(nums, start, i - 1);
        quickSort(nums, i + 1, end);
    }

    public static void main(String[] args) {
        //int[] test = new int[]{3,4,-1,1};
        int[] test = new int[] {1, 1000};
        int r = new FirstMissingPositive41().firstMissingPositive(test);
        System.out.print(r);
    }
}
