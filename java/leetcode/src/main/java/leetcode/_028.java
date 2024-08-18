package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _028 {
    public int strStr(String haystack, String needle) {
        if (haystack == null || needle == null) return -1;
        if (haystack.isEmpty() && needle.isEmpty()) return 0;
        int lenH = haystack.length(), lenN = needle.length(), l = 0, r = 0, i = 0;
        while (i < lenH) {
            l = i; r = 0;
            while (r < lenN && l < lenH) {
                if (haystack.charAt(l) != needle.charAt(r)) {
                    break;
                }
                l++;
                r++;
            }
            if (r == lenN) {
                return i;
            }
            i++;
        }
        return -1;
    }

    static public void main(String[] args) {
//        int i = new _028().strStr("hello", "ll");
        int i = new _028().strStr("aaa", "aaaa");
        System.out.println(i);
    }
}
