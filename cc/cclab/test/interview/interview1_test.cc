
#include <vector>
#include <utility>
#include <set>

#include <gtest/gtest.h>

using namespace std;

class Interview1Test : public testing::Test {};

bool dfs(const vector<vector<char>> &grids, const std::string &target, int x, int y, string &path,
         set<pair<int, int>> &visited) {
            cout << "x: " << x << ", y: " << y << endl;
    if (x < 0 || x >= grids.size() || y < 0 || y >= grids[0].size()) {
        return false;
    }
    if (visited.find({x, y}) != visited.end()) {
        return false;
    }
    if (path.find(target) != string::npos) {
        return true;
    }
    path.push_back(grids[x][y]);
    cout<<"path: "<<path<<endl;
    visited.insert({x, y});
    vector<pair<int, int>> dirs = {{-1, 0}, {1, 0}, {0, -1}, {0, 1}};
    for (auto& p : dirs) {
        if (dfs(grids, target, x + p.first, y + p.second, path, visited)) {
            return true;
        }
    }
    visited.erase({x, y});
    path.pop_back();
    return false;
}

string findPath(const vector<vector<char>> &grids, const std::string &target) {
    for (int i = 0; i < grids.size(); ++i) {
        for (int j = 0; j < grids[0].size(); ++j) {
            string path;
            set<pair<int, int>> visited;
            if (dfs(grids, target, i, j, path, visited)) {
                return path;
            }
        }
    }
    return "";
};

TEST_F(Interview1Test, Test1) {
    vector<vector<char>> grids = {
        {'a', 'b', 'c', 'd'},
        {'e', 'f', 'g', 'h'},
        {'i', 'j', 'k', 'l'},
        {'m', 'n', 'o', 'p'}
    };
    string target = "abcgkop";
    string path = findPath(grids, target);
    ASSERT_EQ(path, "abcgkop");
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}