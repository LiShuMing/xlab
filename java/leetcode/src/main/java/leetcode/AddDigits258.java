package leetcode;

/**
 * @author : lishuming
 */
public class AddDigits258 {
    public int addDigits(int num) {
        int ret = 0;

        while (num / 10 != 0) {
            ret += num % 10;
            num = num / 10;
        }
        ret += num;

        if (ret < 10) {
            return ret;
        }

        return addDigits(ret);
    }

    public static void main(String[] args) {
        int ret = new AddDigits258().addDigits(38);
        System.out.println(ret);
    }
}
