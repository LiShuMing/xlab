package leetcode;

/**
 * @author : lishuming
 */
public class PlusOne66 {
    public int[] plusOne(int[] digits) {
        int rlen = digits.length;
        if (rlen == 0) {
            return digits;
        }

        int up = 1, r, i = rlen;
        while (up != 0 && i > 0) {
            System.out.println(i);

            r = digits[i - 1] + up;

            if (r == 10) {
                up = 1;
            } else {
                up = 0;
            }
            digits[i - 1] = r % 10;

            i--;
        }

        int[] ret;
        if (up == 1) {
            ret = new int[rlen + 1];
            ret[0] = 1;
            for (int j = 1; j < rlen + 1; j++) {
                ret[j] = digits[j - 1];
            }
        } else {
            ret = new int[rlen];
            for (int j = 0; j < rlen; j++) {
                ret[j] = digits[j];
            }
        }

        return ret;
    }

    public static void main(String[] args) {
        int[] t = new int[] {9, 9};
        int[] rs = new PlusOne66().plusOne(t);

        for (int i = 0; i < rs.length; i++) {
            System.out.println(rs[i]);
        }

    }
}
