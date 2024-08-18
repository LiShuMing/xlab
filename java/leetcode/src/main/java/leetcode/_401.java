package leetcode;

import java.util.ArrayList;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _401 {
    public List<String> readBinaryWatch(int num) {
        List<String> res = new ArrayList<>();
        for (int i = 0; i < 12; i++) {
            for (int j = 0; j < 60; j++) {
                if (countBitsOfNum(i) + countBitsOfNum(j) == num) {
                    if (j < 10) {
                        res.add(i + ":0" + j);
                    } else {
                        res.add(i + ":" + j);
                    }
                }
            }
        }
        return res;
    }

    private int countBitsOfNum(int num) {
        int count = 0, v = 0;
        for (int i = 0; i < 32; i++) {
            v = num & 1;
            if (v == 1) count++;
            num >>= 1;
        }
        return count;
    }
}
