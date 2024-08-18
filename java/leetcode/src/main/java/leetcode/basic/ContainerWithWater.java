package leetcode.basic;

/**
 * @author : lishuming
 */
public class ContainerWithWater {
    public int soluction(int[] height) {

        int length = height.length, l = 0, r = length - 1, h = 0, max = 0;

        while (l < r) {
            h = Math.min(height[l], height[r]);
            max = Math.max(max, h * (r - l + 1));
            while (height[r] <= h && l < r) { r--; }
            while (height[l] <= h && l < r) { l++; }
        }
        return max;
    }
}
