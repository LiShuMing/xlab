package leetcode;

import java.util.ArrayList;
import java.util.List;

/**
 * @author shuming.lsm
 * @version 2019/12/03
 */
public class _234 {
    public boolean isPalindrome(ListNode head) {
        int len = 0;
        ListNode t = head, t2 = head;
        while (t != null) {
            len ++;
            t = t.next;
        }
        int i = 0;
        List<Integer> list = new ArrayList<>();
        while (i < len / 2) {
            list.add(t2.val);
            t2 = t2.next;
            i++;
        }
        int j = 1;
        if (len % 2 == 1) {
            t2 = t2.next;
            i++;
            j++;
        }
        while (t2 != null) {
           if (t2.val != list.get(i - j))  {
               return false;
           }
           t2 = t2.next;
           j++;
        }
        return true;
    }

    public static void main(String[] args) {
        ListNode l = new ListNode(-129);
        ListNode l2 = new ListNode(-129);
        l.next = l2;
        boolean r = new _234().isPalindrome(l);
        System.out.println(r);
    }
}
