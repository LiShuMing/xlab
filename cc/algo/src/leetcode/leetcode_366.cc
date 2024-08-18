#include "../include/fwd.h"

/**
Given the root of a binary tree, collect a tree's nodes as if you were doing this:

1. Collect all the leaf nodes.
2. Remove all the leaf nodes.
3. Repeat until the tree is empty.

Example 1:
Input: root = [1,2,3,4,5]
Output: [[4,5,3],[2],[1]]

Explanation:
[[4,5,3] are the leaf nodes at the first level.
[2] is the leaf node at the second level.
[1] is the leaf node at the third level.

Example 2:
Input: root = [1]
Output: [[1]]

Constraints:
The number of nodes in the tree is in the range [1, 100].
-100 <= Node.val <= 100
 */
class Solution {
public:
    vector<vector<int>> findLeaves(TreeNode* root) {
        vector<vector<int>> ans;
        // bfs
        queue<pair<TreeNode*, int>> q;
        q.push({root, 0});
        while (!q.empty()) {
            TreeNode* node = q.front().first;
            int level = q.front().second;
            q.pop();
            if (!node) continue;
            if (level == ans.size()) {
                ans.push_back(vector<int>());
            }
            ans[level].push_back(node->val);
            if (node->left) {
                q.push({node->left, level + 1});
            }
            if (node->right) {
                q.push({node->right, level + 1});
            }
        }
        reverse(ans.begin(), ans.end());
        return ans;
    }

    vector<vector<int> > findLeavesDfs(TreeNode* root) {
        vector<vector<int> > ans;
        dfs(root, ans);
        return ans;
    }
    
private:
    // Returns the height of the node (distance from node to farthest leaf)
    // Height 0 means the node is a leaf
    int dfs(TreeNode* node, vector<vector<int> >& ans) {
        if (!node) return -1;  // Base case: null nodes have height -1
        
        // Calculate height from bottom up
        int leftHeight = dfs(node->left, ans);
        int rightHeight = dfs(node->right, ans);
        int height = 1 + max(leftHeight, rightHeight);
        
        // Ensure we have enough levels in the answer
        if (height == ans.size()) {
            ans.push_back(vector<int>());
        }
        
        // Add current node to its corresponding level based on height
        ans[height].push_back(node->val);
        
        return height;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(1, new TreeNode(2, new TreeNode(4), new TreeNode(5)), new TreeNode(3, new TreeNode(6), new TreeNode(7)));
    vector<vector<int>> ans = solution.findLeaves(root);
    cout << "ans: ";
    for (const auto& vec : ans) {
        cout << "[";
        for (const auto& num : vec) {
            cout << num << " ";
        }
        cout << "]";
    }
    ans = solution.findLeavesDfs(root);
    cout << "ansDfs: ";
    for (const auto& vec : ans) {
        cout << "[";
        for (const auto& num : vec) {
            cout << num << " ";
        }
        cout << "]";
    }
    cout << endl;
    return 0;
}