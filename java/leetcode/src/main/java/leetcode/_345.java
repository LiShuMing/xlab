package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _345 {
    char[] letter = new char[] {'a','e','i','o','u','A','E','I','O','U'};
    private boolean isMetaLetter(char c) {
        for (char l: letter) {
            if (c == l) return true;
        }
        return false;
    }

    public String reverseVowels(String s) {
        if (s == null) return null;
        char c;
        char[] r = s.toCharArray();
        int p = 0, q = s.length() - 1;
        while (p < q) {
            while (!isMetaLetter(s.charAt(p)) && p < q) p++;
            while (!isMetaLetter(s.charAt(q)) && p < q) q--;
            c = s.charAt(p);
            r[p++] = s.charAt(q);
            r[q--] = c;
        }
        return new String(r);
    }
}
