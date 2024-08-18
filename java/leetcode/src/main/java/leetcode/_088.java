package leetcode;

import java.util.Arrays;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _088 {
    public void merge(int[] nums1, int m, int[] nums2, int n) {
        System.arraycopy(nums2, 0, nums1, m, n);
        Arrays.sort(nums1);
    }

    public void merge2(int[] nums1, int m, int[] nums2, int n) {
        int[] copy = new int[m];
        System.arraycopy(nums1, 0, copy, 0, m);

        int i = 0, j = 0, k = 0;
        while (i + j < m + n) {
            if (j >= n) {
                nums1[k++] = copy[i++];
                continue;
            }
            if (i >= m) {
                nums1[k++] = nums2[j++];
                continue;
            }
            if (copy[i] < nums2[j]) {
                nums1[k++] = copy[i++];
            } else {
                nums1[k++] = nums2[j++];
            }
        }
    }
}
