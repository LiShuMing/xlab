package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _008 {
    public int myAtoi(String str) {
        if (str == null || str.isEmpty()) return 0;
        int i = 0, flag = 0, res = 0, mod = 0, len = str.length();
        while (str.charAt(i) == ' ') {
            i++;
            if (i == len) {
                return 0;
            }
        }

        if (str.charAt(i) == '+' ) {
            flag = 1;
            i++;
        } else if (str.charAt(i) >= '0' && str.charAt(i) <= '9') {
            flag = 1;
        } else if (str.charAt(i) == '-') {
            flag = -1;
            i++;
        } else {
            return 0;
        }
        System.out.println(flag);

        while (i < str.length()) {
            if (str.charAt(i) < '0' || str.charAt(i) > '9') {
                break;
            }
            mod = str.charAt(i) - '0';
            if (flag == 1 && (res > Integer.MAX_VALUE / 10 || (res == Integer.MAX_VALUE / 10 && mod > Integer.MAX_VALUE % 10))) {
                return Integer.MAX_VALUE;
            }
            System.out.println(flag + ":" + res);
            if (flag == -1 && (-res < Integer.MIN_VALUE / 10 || (-res == Integer.MIN_VALUE / 10 && -mod < Integer.MIN_VALUE % 10))) {
                System.out.println("!!!!");
                return Integer.MIN_VALUE;
            }
            res = res * 10 + mod;
            i++;
        }
        return res * flag;
    }

    public int myAtoi2(String str) {
        if (str == null) return 0;
        str = str.trim();
        if (str.length() == 0) return 0;
        int i = 0;
        //2.判断数字的符号
        int flag = 1;
        char ch = str.charAt(i);
        if (ch == '+') {
            i++;
        } else if (ch == '-') {
            flag = -1;
            i++;
        }
        //3.找出数字部分
        int res = 0;
        for (; i < str.length(); i++) {
            ch = str.charAt(i);
            if (ch < '0' || ch > '9')
                break;
            //溢出判断
            if (flag > 0 && res > Integer.MAX_VALUE / 10)
                return Integer.MAX_VALUE;
            if (flag > 0 && res == Integer.MAX_VALUE / 10 && ch - '0' > Integer.MAX_VALUE % 10)
                return Integer.MAX_VALUE;
            System.out.println(flag + ":" + res);
            if (flag < 0 && -res < Integer.MIN_VALUE / 10)
                return Integer.MIN_VALUE;
            if (flag < 0 && -res == Integer.MIN_VALUE / 10 && -(ch - '0') < Integer.MIN_VALUE % 10)
                return Integer.MIN_VALUE;
            res = res * 10 + ch - '0';
        }
        return res * flag;
    }

    public static void main(String[] args) {
//        int r = new _008().myAtoi(" 0000000000012345678");
        System.out.println(Integer.MIN_VALUE);
        int r = new _008().myAtoi2("-2147483649");
        System.out.println(r);
    }
}
