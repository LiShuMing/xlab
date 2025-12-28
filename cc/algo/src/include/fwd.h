#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <set>
#include <map>
#include <queue>
#include <stack>
#include <algorithm>
#include <iostream>
#include <string>
#include <cstring>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <numeric>
#include <functional>
#include <cassert>
#include <bitset>
#include <chrono>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <atomic>
#include <memory>
#include <limits>
#include <sstream>
using namespace std;

struct ListNode {
    int val;
    ListNode *next;
    ListNode() : val(0), next(nullptr) {}
    ListNode(int x) : val(x), next(nullptr) {}
    ListNode(int x, ListNode *next) : val(x), next(next) {}
};

struct TreeNode {
    int val;
    TreeNode *left;
    TreeNode *right;
    TreeNode() : val(0), left(nullptr), right(nullptr) {}
    TreeNode(int x) : val(x), left(nullptr), right(nullptr) {}
    TreeNode(int x, TreeNode *left, TreeNode *right) : val(x), left(left), right(right) {}
};

struct NaryTreeNode {
    int val;
    vector<NaryTreeNode*> children;
    NaryTreeNode() : val(0), children(vector<NaryTreeNode*>()) {}
    NaryTreeNode(int x) : val(x), children(vector<NaryTreeNode*>()) {}
    NaryTreeNode(int x, vector<NaryTreeNode*> children) : val(x), children(children) {}
};

template <typename T>
string strJoin(const vector<T>& v, const string& delimiter) {
    stringstream ss;
    ss.precision(10);
    ss.setf(ios::fixed, ios::floatfield);
    for (int i = 0; i < v.size(); i++) {
        if (i != 0) {
            ss << delimiter;
        }
        ss << v[i];
    }
    return ss.str();
} 

template <typename T>
void printVector(const vector<T>& v) {
    for (const auto& elem : v) {
        std::cout << elem << " ";
    }
    std::cout << std::endl;
}