package leetcode.array;

/**
 * @author : lishuming
 */
public class RemoveDuplicate {
    public static int solution(int[] arr) {
        int length = arr.length;
        if (length <= 1) {
            return length;
        }

        int i = 1, j = 1, pre = arr[0];

        while (i < length) {
            if (pre != arr[i]) {
                if (i != j) {
                    arr[j] = arr[i];
                }
                j++;
                pre = arr[i];
            }
            i++;
        }
        return j;
    }
}
