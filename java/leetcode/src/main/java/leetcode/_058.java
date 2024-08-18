package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/02
 */
public class _058 {
  public int lengthOfLastWord(String s) {
    if (s == null || s.isEmpty()) return 0;
    int l = 0;
    for (char c: s.trim().toCharArray()) {
      l++;
      if (c == ' ') {
        l = 0;
      }
    }
    return l;
  }

  public static void main(String[] args) {
    String t = "Hello World";
    System.out.println(new _058().lengthOfLastWord(t));
  }
}
