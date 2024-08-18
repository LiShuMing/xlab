package leetcode.linklist;

/**
 * @author : lishuming
 */
public class LinkedNode {
    private int val;
    public LinkedNode next = null;

    public LinkedNode(int x) {
        val = x;
    }

    public int getVal() {
        return val;
    }

    public void setVal(int val) {
        this.val = val;
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append(val);
        LinkedNode node = this.next;
        while (node != null) {
            sb.append("->");
            sb.append(node.getVal());
            node = node.next;
        }
        return sb.toString();
    }
}
