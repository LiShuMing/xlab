package leetcode;

/**
 * @author : lishuming
 */
public class IsPalindrome125 {
    public boolean isPalindrome(String s) {
        int i = 0, len = s.length(), j = len - 1;

        char l, r;
        while (i < j) {
            while (!Character.isLetterOrDigit(s.charAt(i)) && i < j) {
                i++;
            }
            l = Character.toLowerCase(s.charAt(i));

            while (!Character.isLetterOrDigit(s.charAt(j)) && j > i) {
                j--;
            }
            r = Character.toLowerCase(s.charAt(j));

            if (r != l) {
                return false;
            }
            i++;
            j--;
        }

        return true;
    }

    public static void main(String[] args) {
        //boolean ret = new IsPalindrome125().isPalindrome("A man, a plan, a canal: Panama");
        //boolean ret = new IsPalindrome125().isPalindrome(".,");
        boolean ret = new IsPalindrome125().isPalindrome("0P");
        System.out.println(ret);
    }
}
