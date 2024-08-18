package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _342 {
    public boolean isPowerOfFour(int num) {
        if (num <= 0) return false;
        int mod = 0;
        while (num != 1) {
            mod = num % 4;
            if (mod != 0) {
                return false;
            }
            num = num / 4;
        }
        return true;
    }
}
