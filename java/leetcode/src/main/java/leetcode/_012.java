package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _012 {
    public String intToRoman(int num) {
        StringBuilder sb = new StringBuilder();
        int d = num / 1000;
        while (d-- > 0) {
            sb.append("M");
        }

        int r = num % 1000;
        if (r >= 900) {
           sb.append("CM");
            r %= 900;
        } else if (r >= 500) {
            sb.append("D");
            r %= 500;
        } else if (r >= 400) {
            sb.append("CD");
            r %= 400;
        }
        d = r / 100;
        while (d-- > 0) {
            sb.append("C");
        }

        r = r % 100;
        if (r >= 90) {
            sb.append("XC");
            r %= 90;
        } else if (r >= 50) {
            sb.append("L");
            r %= 50;
        } else if (r >= 40) {
            sb.append("XL");
            r %= 40;
        }
        d = r / 10;
        while (d-- > 0) {
            sb.append("X");
        }

        r = r % 10;
        if (r >= 9) {
            sb.append("IX");
            r %= 9;
        } else if (r >= 5) {
            sb.append("V");
            r %= 5;
        } else if (r >= 4) {
            sb.append("IV");
            r %= 4;
        }
        while (r-- >0) {
            sb.append("I");
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        String r = new _012().intToRoman(1994);
        System.out.println(r);
    }
}
