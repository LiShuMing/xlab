package leetcode;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * @author : lishuming
 */
public class FindWords500 {
    public String[] findWords(String[] words) {
        char[] row1 = new char[] {'q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'};
        char[] row2 = new char[] {'a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'};
        char[] row3 = new char[] {'z', 'x', 'c', 'v', 'b', 'n', 'm'};

        Map<Character, Integer> m = new HashMap<>();
        for (char c : row1) {
            m.put(c, 1);
        }
        for (char c : row2) {
            m.put(c, 2);
        }
        for (char c : row3) {
            m.put(c, 3);
        }

        List<String> ret = new ArrayList<>();
        for (String s : words) {
            if (s.isEmpty()) {
                break;
            }
            String s1 = s.toLowerCase();
            int flag = 0;
            boolean toAdd = true;
            for (char c : s1.toCharArray()) {
                if (flag == 0) {
                    flag = m.get(c);
                } else if (m.get(c) != flag) {
                    toAdd = false;
                    break;
                }
            }
            if (toAdd) {
                ret.add(s);
            }
        }
        return ret.toArray(new String[0]);
    }

    public static void main(String[] args) {

        String[] strs = new String[] {"Hello", "Alaska", "Dad", "Peace"};
        String[] r = new FindWords500().findWords(strs);
        for (String s : r) {
            System.out.println(s);
        }
    }
}
