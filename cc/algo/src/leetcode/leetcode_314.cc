#include "../include/fwd.h"

/**
Given the root of a binary tree, return the vertical order traversal of its nodes' values. (i.e., from top to bottom, column by column).

If two nodes are in the same row and column, the order should be from left to right.

Example 1:
Input: root = [3,9,20,null,null,15,7]
Output: [[9],[3,15],[20],[7]]

Explanation:
Column -1: only node 9
Column 0: nodes 3 and 15
Column 1: only node 20
Column 2: only node 7

Example 2:
Input: root = [3,9,8,4,0,1,7]
Output: [[4],[9],[3,0,1],[8],[7]]

Example 3:
Input: root = [3,9,8,4,0,1,7,null,null,null,2,5]
Output: [[4],[9,5],[3,0,1],[8,2],[7]]

Constraints:
The number of nodes in the tree is in the range [0, 100].
-100 <= Node.val <= 100
 */
class Solution {
public:
    struct Point {
        TreeNode* node;
        int x, y;
        Point(TreeNode* node, int x, int y) : node(node), x(x), y(y) {}
        bool operator>(const Point& other) const {
            if (x != other.x) {
                return x > other.x;
            }
            if (y != other.y) {
                return y > other.y;
            }
            return node->val > other.node->val;
        }
    };
    vector<vector<int>> verticalOrder(TreeNode* root) {
        if (!root) {
            return {};
        }
        priority_queue<Point, vector<Point>, greater<Point>> pq;
        pq.push(Point(root, 0, 0));
        unordered_map<int, vector<int>> ans;
        while (!pq.empty()) {
            Point p = pq.top();
            pq.pop();
            ans[p.x].push_back(p.node->val);
            // left
            if (p.node->left) {
                pq.push(Point(p.node->left, p.x - 1, p.y + 1));
            }
            // right
            if (p.node->right) {
                pq.push(Point(p.node->right, p.x + 1, p.y + 1));
            }
        }
        vector<vector<int>> result;
        for (auto& [_, vals] : ans) {
            result.push_back(vals);
        }
        return result;
    }
};

int main() {
    Solution solution;
    TreeNode* root = new TreeNode(3, new TreeNode(9), new TreeNode(20, new TreeNode(15), new TreeNode(7)));
    vector<vector<int>> ans = solution.verticalOrder(root);
    for (auto& row : ans) {
        printVector(row);
    }
    return 0;
}