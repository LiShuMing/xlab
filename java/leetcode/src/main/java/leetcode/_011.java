package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _011 {
    public int maxArea(int[] height) {
        if (height == null) return 0;
        int p = 0, q = height.length - 1, max = 0;
        while (p < q) {
            max = Math.max(max, Math.min(height[p], height[q]) * (q - p + 1));
            if (height[p] < height[q]) {
                p++;
            } else {
                q--;
            }
        }
        return max;
    }
}
