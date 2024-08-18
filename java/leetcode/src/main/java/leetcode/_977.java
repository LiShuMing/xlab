package leetcode;

import java.util.Arrays;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _977 {
    public int[] sortedSquares(int[] A) {
        if (A == null) return null;
        int[] r = new int[A.length];
        for (int i = 0; i < A.length; i++) {
            r[i] = A[i] * A[i];
        }
        Arrays.sort(r);
        return r;
    }
}
