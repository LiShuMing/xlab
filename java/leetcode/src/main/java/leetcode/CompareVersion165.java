package leetcode;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

/**
 * @author : lishuming
 */
public class CompareVersion165 {
    public int compareVersion(String version1, String version2) {
        if (version1 == null && version2 == null) {
            return 0;
        }
        if (version1 == null) {
            return -1;
        }
        if (version2 == null) {
            return 1;
        }

        List<Integer> list1 = splitVerstion(version1);
        List<Integer> list2 = splitVerstion(version2);
        Iterator<Integer> iter1 = list1.iterator();
        Iterator<Integer> iter2 = list2.iterator();

        Integer integer1, integer2;
        while (iter1.hasNext() || iter2.hasNext()) {
            integer1 = iter1.hasNext() ? iter1.next() : 0;
            integer2 = iter2.hasNext() ? iter2.next() : 0;

            if (integer1 > integer2) {
                return 1;
            } else if (integer1 < integer2) {
                return -1;
            }
        }

        return 0;
    }

    public List<Integer> splitVerstion(String version) {
        List<Integer> ret = new ArrayList<>();

        String[] r = version.split("\\.");
        for (String s : r) {
            ret.add(Integer.parseInt(s));
        }

        return ret;
    }

    public static void main(String[] args) {
        int r = new CompareVersion165().compareVersion("0.1", "0.1.0");
        System.out.println(r);
    }
}
