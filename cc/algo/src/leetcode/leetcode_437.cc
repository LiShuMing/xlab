#include "../include/fwd.h"

/**
* 给定一个二叉树的根节点 root ，和一个整数 targetSum ，求该二叉树里节点值之和等于 targetSum 的 路径 的数目。
* 路径 不需要从根节点开始，也不需要在叶子节点结束，但是路径方向必须是向下的（只能从父节点到子节点）。

 * Definition for a binary tree node.
 * struct TreeNode {
 *     int val;
 *     TreeNode *left;
 *     TreeNode *right;
 *     TreeNode() : val(0), left(nullptr), right(nullptr) {}
 *     TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
 *     TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}
 * };
 */
// class Solution {
// public:
//     int pathSum(TreeNode* root, int targetSum) {
//         if (!root)
//             return 0;

//         return dfs(root, targetSum, 0) +
//                pathSum(root->left, targetSum) +
//                pathSum(root->right, targetSum);
//     }

//     int dfs(TreeNode* r, int remain, int cnt) {
//         if (!r) return 0;
//         // 3 choices
//         // a. choose this node
//         // b. start from this node and go left
//         // c. start from this node and go right
//         int hit = (remain == r->val) ? 1 : 0;
//         return hit + dfs(r->left, remain - r->val, cnt) +
//                dfs(r->right, remain - r->val, cnt);
//     }
// };

class Solution {
public:
    int pathSum(TreeNode* root, int targetSum) {
        if (!root) {
            return 0;
        }
        // visited[x]：根 -> 当前节点这条路径上，前缀和 x 出现的「次数」。
        // 先放入 {0: 1} 代表「空前缀」，这样「路径正好从根开始」的情况才能被数到。
        unordered_map<long long, int> visited{{0, 1}};
        long long prefix = 0;
        return dfs(root, targetSum, prefix, visited);
    }

    int dfs(TreeNode* r, long long target, long long& prefix,
            unordered_map<long long, int>& visited) {
        if (!r) return 0;
        prefix += r->val;

        // 两个前缀和之差等于 target ⇔ 存在一条「以当前节点结尾、和为 target」的路径。
        // 要取「次数」而不是「存不存在」：同一个前缀和可能出现多次，每一次都是一条不同路径。
        auto it = visited.find(prefix - target);
        int ans = (it == visited.end()) ? 0 : it->second;

        ++visited[prefix];  // 把自己加入「当前路径」，供子树查询
        ans += dfs(r->left, target, prefix, visited) +
               dfs(r->right, target, prefix, visited);
        --visited[prefix];  // 回溯：离开本节点后，它就不在当前路径上了
        prefix -= r->val;   // 回溯：前缀和也必须还原，否则兄弟子树会拿到被污染的值
        return ans;
    }
};

int main() {
    // 样例一：[10,5,-3,3,2,null,11,3,-2,null,1], targetSum = 8 -> 3
    TreeNode n10(10), n5(5), nm3(-3), n3(3), n2(2), n11(11), n3b(3), nm2(-2), n1(1);
    n10.left = &n5;
    n10.right = &nm3;
    n5.left = &n3;
    n5.right = &n2;
    nm3.right = &n11;
    n3.left = &n3b;
    n3b.right = &nm2;
    n2.right = &n1;

    // 样例二：1 -> (2, 3)，target = 3 -> 2（路径 [1,2] 和 [3]）
    // 这一组专门用来抓「只漏 prefix 回溯」的错：左子树走完不还原，右子树就会从错误的前缀和继续算。
    TreeNode one(1), two(2), three(3);
    one.left = &two;
    one.right = &three;

    // 样例三：单节点 5，target = 5 -> 1
    TreeNode single(5);

    const struct {
        TreeNode* root;
        int target;
        int expect;
    } cases[] = {{&n10, 8, 3}, {&one, 3, 2}, {&single, 5, 1}, {nullptr, 1, 0}};

    Solution solution;
    int failed = 0;
    for (const auto& c : cases) {
        const int got = solution.pathSum(c.root, c.target);
        cout << "pathSum(target=" << c.target << ") = " << got << "  expect " << c.expect
             << (got == c.expect ? "  OK" : "  FAIL") << endl;
        if (got != c.expect) ++failed;
    }
    cout << (failed == 0 ? "leetcode_437: all checks passed" : "leetcode_437: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
