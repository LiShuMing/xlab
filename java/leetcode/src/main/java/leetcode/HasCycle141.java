package leetcode;

/**
 * @author : lishuming
 */
public class HasCycle141 {
    public boolean hasCycle(ListNode head) {
        if (head == null || head.next == null || head.next.next == null) {
            return false;
        }

        ListNode pNext = head;
        ListNode pNextNext = head;
        while (pNext != null && pNext.next != null && pNextNext != null && pNextNext.next != null
            && pNextNext.next.next != null) {
            pNext = pNext.next;
            pNextNext = pNextNext.next.next;

            if (pNext == pNextNext) {
                return true;
            }
        }

        return false;
    }

    public static void main(String[] args) {

    }
}
