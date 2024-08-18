package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _191 {
    // you need to treat n as an unsigned value
    public int hammingWeight(int n) {
        int count = 0, v = 0;
        for (int i = 0; i < 32; i++) {
            v = n & 1;
            if (v == 1) {
                count++;
            }
            n >>= 1;
        }
        return count;
    }
}
