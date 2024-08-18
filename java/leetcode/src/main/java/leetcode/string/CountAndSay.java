package leetcode.string;

/**
 * @author : lishuming
 */
public class CountAndSay {
    public String countAndSay(int n) {
        String s = String.valueOf(n);
        if (s.length() <= 1) {
            return s;
        }

        StringBuilder sb = new StringBuilder();
        Integer lastInterger = Integer.parseInt(s.substring(0, 1));
        int count = 1;
        for (int i = 1; i < s.length(); i++) {
            Integer a = Integer.parseInt(s.substring(i, i + 1));
            if (!a.equals(lastInterger)) {
                sb.append(String.valueOf(count)).append(String.valueOf(lastInterger));
                count = 1;
            } else {
                count++;
            }
            lastInterger = a;
        }
        sb.append(String.valueOf(count)).append(String.valueOf(lastInterger));

        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(new CountAndSay().countAndSay(11223));
    }
}
