package leetcode;

/**
 * @author : lishuming
 */
public class DetectCapitalUse520 {
    public boolean detectCapitalUse(String word) {
        if (word.length() <= 1) {
            return true;
        }

        if (Character.isUpperCase(word.charAt(0))) {
            if (Character.isLowerCase(word.charAt(1))) {
                for (int i = 1; i < word.length(); i++) {
                    if (!Character.isLowerCase(word.charAt(i))) {
                        return false;
                    }
                }
            } else {
                for (int i = 1; i < word.length(); i++) {
                    if (!Character.isUpperCase(word.charAt(i))) {
                        return false;
                    }
                }
            }
        } else {
            for (char c : word.toCharArray()) {
                if (!Character.isLowerCase(c)) {
                    return false;
                }
            }
        }

        return true;
    }

    public static void main(String[] args) {
        boolean r = new DetectCapitalUse520().detectCapitalUse("Addajlk");
        System.out.println(r);
    }
}
