package leetcode;

/**
 * @author : lishuming
 */
public class Reverse7 {
    public int reverse(int x) {
        int ret = 0;

        boolean sign = false;
        if (x < 0) {
            sign = true;
            x = -x;
        }

        while (x != 0) {
            int result = 10 * ret + x % 10;
            if (result / 10 != ret) {
                return 0;
            }
            ret = result;
            x = x / 10;
        }

        return sign ? -ret : ret;
    }

    public static void main(String[] args) {
        int ret = new Reverse7().reverse(-132);
        //int ret = new Reverse7().reverse(1534236469);
        System.out.println(ret);
    }
}
