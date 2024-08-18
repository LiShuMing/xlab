package leetcode.basic;

import java.util.HashMap;

/**
 * @author : lishuming
 */
public class Roman2Int {
    public int solution(String r) {
        if (r == null || r.isEmpty()) { return 0; }
        HashMap<Character, Integer> m = new HashMap<>();
        m.put('I', 1);
        m.put('V', 5);
        m.put('X', 10);
        m.put('L', 50);

        int result = 0;
        for (int i = 0; i < r.length(); i++) {
            if (!m.containsKey(r.charAt(i))) {
                System.out.println(r.charAt(i));
                return 0;
            }
            result = result + m.get(r.charAt(i));
        }

        return result;
    }
}
