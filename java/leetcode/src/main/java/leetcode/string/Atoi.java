package leetcode.string;

/**
 * @author : lishuming
 */
public class Atoi {
    public int solution(String s) {
        int i = 0, sign = 1, result = 0;
        int len = s.length();
        while (s.charAt(i) == ' ') {
            i++;
        }

        if (s.charAt(i) == '+') {
            sign = 1;
            i++;
        } else if (s.charAt(i) == '-') {
            sign = -1;
            i++;
        }

        for (; i < len; i++) {
            int tmp = s.charAt(i) - '0';
            result = result * 10 + tmp;

            if (result > Integer.MAX_VALUE || result < Integer.MIN_VALUE) {
                return 0;
            }
        }
        if (sign == -1) {
            result = sign * result;
        }

        return result;
    }
}
