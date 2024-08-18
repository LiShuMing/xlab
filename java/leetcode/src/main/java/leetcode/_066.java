package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _066 {
    public int[] plusOne(int[] digits) {
        boolean all9 = true;
        for (int i : digits) {
            if (i != 9) {
                all9 = false;
                break;
            }
        }
        if (all9) {
            int[] ret = new int[digits.length + 1];
            ret[0] = 1;
            for (int i = 1; i < ret.length; i++) {
                ret[i] = 0;
            }
            return ret;
        }

        int r = 1, i = digits.length - 1, v = 0, s = 0;
        while (r != 0) {
            s = digits[i] + r;
            v = s % 10;
            r = s / 10;
            digits[i--] = v;
        }
        return digits;
    }
}
