package leetcode;

import java.util.SortedSet;
import java.util.TreeSet;

/**
 * @author : lishuming
 */
public class ContainsNearbyAlmostDuplicate220 {
    public static boolean solution(int[] nums, int k, int t) {
        int len = nums.length;

        if (len < k) {
            for (int i = 0; i < len; i++) {
                for (int j = i; j < len; j++) {
                    if (Math.abs(nums[j] - nums[i]) <= t) {
                        return true;
                    }
                }
            }
            return false;
        }

        for (int i = 0; i < len - 1; i++) {
            int b = i + k > len - 1 ? len : i + k + 1;

            for (int j = i + 1; j < b; j++) {
                if ((nums[i] ^ nums[j]) < 0 && Math.abs(nums[i] - nums[j]) < Math.max(nums[i], nums[j])) {
                    long tmp = (long)nums[i] - (long)nums[j];
                    if (tmp > 0) {
                        if (tmp >= Integer.MAX_VALUE) {
                            continue;
                        }
                    } else {
                        if (tmp <= Integer.MIN_VALUE) {
                            continue;
                        }
                    }
                }

                if (Math.abs(nums[i] - nums[j]) <= t) {
                    return true;
                }
            }
        }

        return false;
    }

    public static boolean solutionV2(int[] nums, int k, int t) {
        if (k <= 0 || t < 0) {
            return false;
        }

        SortedSet<Long> sortedSet = new TreeSet<>();
        for (int i = 0; i < nums.length; i++) {
            if (i > k) {
                sortedSet.remove((long)nums[i - k - 1]);
            }

            SortedSet<Long> tmp = sortedSet.subSet((long)nums[i] - t, (long)nums[i] + t + 1);

            if (!tmp.isEmpty()) {
                for (Long tt : tmp) {
                    System.out.println(tt);
                }
                return true;
            }

            tmp.add((long)nums[i]);
        }
        return false;
    }

    public static void main(String[] args) {
        System.out.println(Math.abs(-1 - 2147483647));
        System.out.println(Math.abs(-1 - 2147483647) < 10);

        SortedSet<Long> sortedSet = new TreeSet<>();
        sortedSet.add(11L);
        sortedSet.add(13L);
        sortedSet.add(14L);
        sortedSet.add(15L);
        sortedSet.add(16L);

        SortedSet<Long> tmp = sortedSet.subSet(10L, 20L);
        for (Long t : tmp) {
            System.out.println(t);
        }

        int[] test = new int[] {-2147483647, 2147483647};
        //System.out.println(solutionV2(test, 1, 2147483647));

        int[] test2 = new int[] {1, 5, 9, 1, 5, 9};
        System.out.println(solutionV2(test2, 2, 3));
    }
}
