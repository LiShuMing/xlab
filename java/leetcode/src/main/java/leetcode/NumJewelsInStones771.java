package leetcode;

import java.util.HashMap;
import java.util.Map;

/**
 * @author : lishuming
 */
public class NumJewelsInStones771 {
    public int numJewelsInStones(String J, String S) {
        Map<Character, Boolean> map = new HashMap<Character, Boolean>();
        for (char t : J.toCharArray()) {
            map.put(t, true);
        }
        int ret = 0;
        for (char t : S.toCharArray()) {
            if (map.containsKey(t)) {
                ret++;
            }
        }
        return ret;
    }

    public static void main(String[] args) {
        int r = new NumJewelsInStones771().numJewelsInStones("aA", "aASAadf");
        System.out.println(r);
    }
}
