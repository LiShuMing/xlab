package leetcode;

/**
 * @author : lishuming
 */
public class FindTheDifference389 {
    public char findTheDifference(String s, String t) {
        char[] h = new char[26];

        for (char a : s.toCharArray()) {
            h[a - 'a']++;
        }

        for (char a : t.toCharArray()) {
            if (h[a - 'a'] <= 0) {
                return a;
            } else {
                h[a - 'a']--;
            }
        }

        // TODO: IMPOSSIBLE
        return 'N';
    }

    public char findTheDifferenceV2(String s, String t) {
        int ret = 0;

        for (char a : s.toCharArray()) {
            ret ^= a - 'a';
        }

        for (char a : t.toCharArray()) {
            ret ^= a - 'a';
        }

        return (char)(ret + 'a');
    }

    public static void main(String[] args) {
        //char r = new FindTheDifference389().findTheDifference("abcd", "abcde");
        char r = new FindTheDifference389().findTheDifferenceV2("abcd", "abcde");
        System.out.println(r);
    }
}
