#include "../include/fwd.h"
/**
给你一个二维整数数组 squares ，其中 squares[i] = [xi, yi, li] 表示一个与 x 轴平行的正方形的左下角坐标和正方形的边长。

找到一个最小的 y 坐标，它对应一条水平线，该线需要满足它以上正方形的总面积 等于 该线以下正方形的总面积。

答案如果与实际答案的误差在 10-5 以内，将视为正确答案。

注意：正方形 可能会 重叠。重叠区域只 统计一次 
 */

struct Event {
    int x;
    int y_low;
    int y_high;
    int type; // +1 for left edge, -1 for right edge

    bool operator<(const Event& other) const {
        return x < other.x;
    }
};

class Solution {
public:
    double separateSquares(vector<vector<int>>& squares) {
        // 1. Collect all unique y-coordinates to define horizontal slabs
        vector<int> y_coords;
        for (const auto& s : squares) {
            y_coords.push_back(s[1]);
            y_coords.push_back(s[1] + s[2]);
        }
        sort(y_coords.begin(), y_coords.end());
        y_coords.erase(unique(y_coords.begin(), y_coords.end()), y_coords.end());

        // 2. Calculate L(y) for each slab defined by [y_coords[i], y_coords[i+1]]
        // L(y) is the length of union of x-intervals covering this slab.
        int n = y_coords.size();
        vector<double> slab_widths(n - 1);
        double total_area = 0;

        for (int i = 0; i < n - 1; ++i) {
            int y_start = y_coords[i];
            int y_end = y_coords[i + 1];
            
            // Find all x-intervals [x, x+l] that cover this y-slab
            vector<pair<int, int>> intervals;
            for (const auto& s : squares) {
                if (s[1] <= y_start && s[1] + s[2] >= y_end) {
                    intervals.push_back({s[0], s[0] + s[2]});
                }
            }
            
            // Merge intervals to find union length on x-axis
            slab_widths[i] = calculateUnionLength(intervals);
            total_area += slab_widths[i] * (y_end - y_start);
        }

        // 3. Find the y where accumulated area reaches total_area / 2
        double target_area = total_area / 2.0;
        double current_area = 0;
        for (int i = 0; i < n - 1; ++i) {
            double next_area = slab_widths[i] * (y_coords[i + 1] - y_coords[i]);
            if (current_area + next_area >= target_area - 1e-9) {
                // The target y lies within this slab [y_coords[i], y_coords[i+1]]
                // Since L(y) is constant here: current_area + L(y) * (y - y_coords[i]) = target_area
                return y_coords[i] + (target_area - current_area) / slab_widths[i];
            }
            current_area += next_area;
        }

        return y_coords.back();
    }

private:
    double calculateUnionLength(vector<pair<int, int>>& intervals) {
        if (intervals.empty()) return 0;
        sort(intervals.begin(), intervals.end());
        
        double length = 0;
        int current_start = intervals[0].first;
        int current_end = intervals[0].second;
        
        for (size_t i = 1; i < intervals.size(); ++i) {
            if (intervals[i].first < current_end) {
                current_end = max(current_end, intervals[i].second);
            } else {
                length += current_end - current_start;
                current_start = intervals[i].first;
                current_end = intervals[i].second;
            }
        }
        length += current_end - current_start;
        return length;
    }
};


// Node for Segment Tree to maintain x-axis coverage
struct Node {
    int cnt = 0;
    double len = 0;
};

class Solution2 {
public:
    double separateSquares(vector<vector<int>>& squares) {
        vector<int> x_coords;
        struct Event {
            int y;
            int x1, x2;
            int type; // +1 for start, -1 for end
            bool operator<(const Event& other) const { return y < other.y; }
        };
        vector<Event> events;

        for (const auto& s : squares) {
            x_coords.push_back(s[0]);
            x_coords.push_back(s[0] + s[2]);
            events.push_back({s[1], s[0], s[0] + s[2], 1});
            events.push_back({s[1] + s[2], s[0], s[0] + s[2], -1});
        }

        // 1. Discretize X coordinates
        sort(x_coords.begin(), x_coords.end());
        x_coords.erase(unique(x_coords.begin(), x_coords.end()), x_coords.end());
        int m = x_coords.size();
        
        sort(events.begin(), events.end());

        // 2. Segment Tree Setup
        vector<Node> tree(4 * m);
        auto update = [&](auto self, int node, int l, int r, int ql, int qr, int val) -> void {
            if (ql <= x_coords[l] && x_coords[r] <= qr) {
                tree[node].cnt += val;
            } else {
                int mid = (l + r) / 2;
                if (ql < x_coords[mid]) self(self, 2 * node, l, mid, ql, qr, val);
                if (qr > x_coords[mid]) self(self, 2 * node + 1, mid, r, ql, qr, val);
            }
            
            // Push up logic
            if (tree[node].cnt > 0) {
                tree[node].len = x_coords[r] - x_coords[l];
            } else if (r - l > 1) {
                tree[node].len = tree[2 * node].len + tree[2 * node + 1].len;
            } else {
                tree[node].len = 0;
            }
        };

        // 3. First pass: Calculate total area
        double total_area = 0;
        for (int i = 0; i < events.size() - 1; ++i) {
            update(update, 1, 0, m - 1, events[i].x1, events[i].x2, events[i].type);
            total_area += tree[1].len * (events[i + 1].y - events[i].y);
        }

        // 4. Second pass: Find the y-coordinate that splits the area
        // Reset tree for second pass
        fill(tree.begin(), tree.end(), Node{0, 0.0});
        double target_area = total_area / 2.0;
        double current_area = 0;

        for (int i = 0; i < events.size() - 1; ++i) {
            update(update, 1, 0, m - 1, events[i].x1, events[i].x2, events[i].type);
            double next_slab_area = tree[1].len * (events[i + 1].y - events[i].y);
            
            if (current_area + next_slab_area >= target_area - 1e-9) {
                // If tree[1].len is 0, it means it's a zero-width gap, just skip
                if (tree[1].len > 0) {
                    return events[i].y + (target_area - current_area) / tree[1].len;
                }
            }
            current_area += next_slab_area;
        }

        return events.back().y;
    }
};

int main() {
    Solution solution;
    vector<vector<int> > squares;
    int arrA[] = {0, 0, 2};
    int arrB[] = {1, 1, 1};
    squares.push_back(vector<int>(arrA, arrA + 3));
    squares.push_back(vector<int>(arrB, arrB + 3));
    cout << solution.separateSquares(squares) << endl;
    return 0;
}
