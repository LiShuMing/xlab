package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/04
 */
public class _050 {
    public double myPow(double x, int n) {
        if (x == 0) return 0;

        if (n < 0) {
            x = 1 / x;
            n = -n;
        }

        return fastPow(x, n);
    }

    private double fastPow(double x, int n) {
       if (n == 0)  {
           return 1;
       }

       double r = fastPow(x, n / 2);
       if (r >= Integer.MAX_VALUE) {
           return Integer.MAX_VALUE;
       }
       if ( r <= Integer.MIN_VALUE) {
           return Integer.MIN_VALUE;
       }
       if (n % 2 == 0) {
           return r * r;
       } else {
           return r * r * x;
       }
    }

    public static void main(String[] args) {
//        double r = new _050().fastPow(0.00001, 2147483647);
//        System.out.println(r);
        String a = null;
        if (a instanceof String) {
            System.out.println("O is string");
        } else {
            System.out.println("O is not string");
        }
    }
}
