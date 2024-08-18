#include "../include/fwd.h"

class NumArray {
public:
    vector<int> prefix;
    NumArray(vector<int>& nums) {
        int n = nums.size();
        prefix.resize(n + 1);
        for (int i = 0; i < n; i++) {
            prefix[i + 1] = prefix[i] + nums[i];
        }
    }
    void update(int index, int val) {
        int n = prefix.size();
        int diff = val - prefix[index + 1] + prefix[index];
        for (int i = index + 1; i < n; i++) {
            prefix[i] += diff;
        }
    }
    int sumRange(int left, int right) {
        return prefix[right + 1] - prefix[left];
    }
};
class NumArrayV2 {
public:
    vector<int> tree;
    int n;
    // use segment tree to implement the num array
    NumArrayV2(vector<int>& nums) {
        n = nums.size();
        tree.resize(4 * n);
        build(1, 0, n - 1, nums);
    }
    void build(int node, int l, int r, vector<int>& nums) {
        if (l == r) {
            tree[node] = nums[l];
            return;
        }
        int mid = (l + r) / 2;
        build(node * 2, l, mid, nums);
        build(node * 2 + 1, mid + 1, r, nums);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }
    int sumRange(int node, int l, int r, int ql, int qr) {
        if (qr < l || r < ql) return 0;
        if (ql <= l && r <= qr) return tree[node];
        int mid = (l + r) / 2;
        int leftSum = sumRange(node * 2, l, mid, ql, qr);
        int rightSum = sumRange(node * 2 + 1, mid + 1, r, ql, qr);
        return leftSum + rightSum;
    }
    int sumRange(int ql, int qr) {
        return sumRange(1, 0, n - 1, ql, qr);
    }
    void update(int index, int val) {
        update(1, 0, n - 1, index, val);
    }
    void update(int node, int l, int r, int index, int val) {
        if (l == r) {
            tree[node] = val;
            return;
        }
        int mid = (l + r) / 2;
        if (index <= mid) update(node * 2, l, mid, index, val);
        else update(node * 2 + 1, mid + 1, r, index, val);
        tree[node] = tree[node * 2] + tree[node * 2 + 1];
    }
};
int main() {
    vector<int> nums = {1, 2, 3, 4, 5};
    NumArray numArray(nums);
    cout << numArray.sumRange(0, 2) << endl;
    cout << numArray.sumRange(1, 3) << endl;
    cout << numArray.sumRange(2, 4) << endl;
    return 0;
}