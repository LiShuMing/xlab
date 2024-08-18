package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _067 {
    public String addBinary(String a, String b) {
        int l = a.length() > b.length()? a.length() : b.length();

        int m = a.length() - 1, n = b.length() - 1, s = 0, v = 0, r = 0;
        char[] aa = a.toCharArray();
        char[] bb = b.toCharArray();
        // Add one char buffer
        char[] ret = new char[l + 1];
        int z = l;
        while (m >= 0 || n >= 0) {
            // initialize s.
            s = 0;
            if (m >= 0) {
                s += aa[m--] - '0';
            }
            if (n >= 0) {
                s += bb[n--] - '0';
            }
            s += r;
            v = s % 2;
            r = s / 2;

            if (v == 0) {
                ret[z--] = '0';
            } else {
                ret[z--] = '1';
            }
        }
        if (r != 0) {
            ret[z--] = '1';
            return new String(ret);
        } else {
            return new String(ret).substring(1);
        }
    }
    static public void main(String[] args) {
        String r = new _067().addBinary("1010", "1011");
        System.out.println(r);
    }
}
