package leetcode;

/**
 * @author : lishuming
 */
public class AddStrings415 {
    public String addStrings(String num1, String num2) {
        if (num1 == null || num2 == null) {
            return null;
        }
        if (num1.isEmpty()) {
            return num2;
        }
        if (num2.isEmpty()) {
            return num1;
        }

        int len1 = num1.length(), len2 = num2.length();

        int isAdd = 0;
        StringBuilder sb = new StringBuilder();
        char c1, c2;
        while (len1 > 0 || len2 > 0) {
            if (len1 <= 0) {
                c1 = '0';
            } else {
                c1 = num1.charAt(len1 - 1);
            }
            if (len2 <= 0) {
                c2 = '0';
            } else {
                c2 = num2.charAt(len2 - 1);
            }

            int t = c1 - '0' + c2 - '0' + isAdd;
            if (t >= 10) {
                isAdd = 1;
            } else {
                isAdd = 0;
            }
            sb.append(t % 10);
            len1--;
            len2--;
        }
        if (isAdd == 1) {
            sb.append("1");
        }

        return sb.reverse().toString();
    }

    public static void main(String[] args) {
        //String s = new AddStrings415().addStrings("123", "1100");
        //String s = new AddStrings415().addStrings("6", "501");
        String s = new AddStrings415().addStrings("99", "9");
        System.out.println(s);
    }
}
