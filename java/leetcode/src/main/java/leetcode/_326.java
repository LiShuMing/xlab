package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _326 {
    public boolean isPowerOfThree(int n) {
        if (n <= 0) return false;
        int mod = 0;
        while (n != 1) {
            mod = n % 3;
            if (mod != 0) {
                return false;
            }
            n = n / 3;
        }
        return true;
    }
}
