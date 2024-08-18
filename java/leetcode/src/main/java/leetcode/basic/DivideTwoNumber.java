package leetcode.basic;

/**
 * @author : lishuming
 */
public class DivideTwoNumber {
    public static int solution(int d1, int d2) {
        long t1 = Math.abs(d1);
        long t2 = Math.abs(d2);

        int res = 0;
        while (t1 >= t2) {

            long tmp = t2, k = 1;
            while (t1 >= tmp << 1) {
                tmp = tmp << 1;
                k <<= 1;
            }
            t1 -= tmp;
            res += k;
        }

        return (d1 < 0) && (d2 < 0) ? res : -res;
    }

}
