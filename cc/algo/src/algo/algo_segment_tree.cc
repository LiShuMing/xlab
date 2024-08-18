#include "../include/fwd.h"

class SegmentTree {
public:
    SegmentTree(vector<int>& nums) {
        n = nums.size();
        tree.resize(4 * n);  // 4*n is safe upper bound
        build(1, 0, n - 1, nums);
    }
    
    // Build segment tree recursively
    void build(int node, int l, int r, vector<int>& nums) {
        if (l == r) {
            tree[node] = nums[l];
            return;
        }
        int mid = (l + r) / 2;
        build(node * 2, l, mid, nums);
        build(node * 2 + 1, mid + 1, r, nums);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];  // sum operation
    }
    
    // Query sum in range [ql, qr]
    int query(int ql, int qr) {
        return query(1, 0, n - 1, ql, qr);
    }
    
    int query(int node, int l, int r, int ql, int qr) {
        if (qr < l || r < ql) return 0;  // no overlap
        if (ql <= l && r <= qr) return tree[node];  // complete overlap
        int mid = (l + r) / 2;
        int leftSum = query(node * 2, l, mid, ql, qr);
        int rightSum = query(node * 2 + 1, mid + 1, r, ql, qr);
        return leftSum + rightSum;
    }
    
    // Point update: set position idx to value val
    void update(int idx, int val) {
        update(1, 0, n - 1, idx, val);
    }
    
    void update(int node, int l, int r, int idx, int val) {
        if (l == r) {
            tree[node] = val;
            return;
        }
        int mid = (l + r) / 2;
        if (idx <= mid) update(node * 2, l, mid, idx, val);
        else update(node * 2 + 1, mid + 1, r, idx, val);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }
    
private:
    vector<int> tree;
    int n;
};

int main() {
    int arr[] = {1, 3, 5, 7, 9, 11};
    vector<int> nums(arr, arr + 6);
    SegmentTree st(nums);
    
    cout << "Original array: ";
    for (size_t i = 0; i < nums.size(); ++i) {
        cout << nums[i];
        if (i < nums.size() - 1) cout << " ";
    }
    cout << endl;
    
    cout << "Sum of [0, 2]: " << st.query(0, 2) << endl;   // 1 + 3 + 5 = 9
    cout << "Sum of [1, 4]: " << st.query(1, 4) << endl;   // 3 + 5 + 7 + 9 = 24
    
    st.update(2, 10);  // change 5 to 10
    cout << "After update [2]=10, sum [0, 2]: " << st.query(0, 2) << endl;  // 1 + 3 + 10 = 14
    
    return 0;
}