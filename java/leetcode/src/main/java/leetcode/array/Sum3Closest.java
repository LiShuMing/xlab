package leetcode.array;

import java.util.Arrays;

/**
 * @author : lishuming
 */
public class Sum3Closest {
    public int solution(int[] array, int target) {
        int length = array.length, curDelta = 0x7fffffff, result = 0;
        Arrays.sort(array);
        for (int i = 0; i < length; i++) {
            int l = i + 1, r = length - 1, delta = 0, sum = 0;
            while (l < r) {
                sum = array[i] + array[l] + array[r];
                delta = Math.abs(sum - target);
                if (delta < 0) {
                    l++;
                } else if (delta == 0) {
                    return 0;
                } else {
                    r--;
                }

                if (delta < curDelta) {
                    result = sum;
                }
            }
        }

        return result;
    }
}
