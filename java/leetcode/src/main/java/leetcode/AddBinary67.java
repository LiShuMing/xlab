package leetcode;

/**
 * @author : lishuming
 */
public class AddBinary67 {
    public String addBinary(String a, String b) {
        int aLen = a.length();
        int bLen = b.length();

        StringBuilder sb = new StringBuilder();
        boolean upDigital = false;
        int ai, bi, r;
        while (aLen > 0 || bLen > 0) {
            if (aLen <= 0) {
                ai = 0;
            } else {
                ai = a.charAt(aLen - 1) - '0';
            }

            if (bLen <= 0) {
                bi = 0;
            } else {
                bi = b.charAt(bLen - 1) - '0';
            }

            if (upDigital) {
                r = ai + bi + 1;
            } else {
                r = ai + bi;
            }

            if (r >= 2) {
                upDigital = true;
                sb.append(String.valueOf(r % 2));
            } else {
                sb.append(String.valueOf(r));
                upDigital = false;
            }

            aLen--;
            bLen--;
        }
        if (upDigital) {
            sb.append(String.valueOf(1));
        }

        return sb.reverse().toString();
    }

    public static void main(String[] args) {
        //System.out.println(new AddBinary67().addBinary("1101", "1011"));
        //System.out.println(new AddBinary67().addBinary("1101", "101"));
        System.out.println(new AddBinary67().addBinary("111", "1"));
    }
}
