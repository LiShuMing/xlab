#include "../include/fwd.h"

class Solution {
public:
    vector<double> cutSquares(vector<int>& square1, vector<int>& square2) {
        // compute the center of the two squares
        double x1 = square1[0] + square1[2] / 2.0;
        double y1 = square1[1] + square1[2] / 2.0;
        double x2 = square2[0] + square2[2] / 2.0;
        double y2 = square2[1] + square2[2] / 2.0;
        // if x1 == x2, then the two squares are parallel
        vector<pair<double, double>> res;
        if (x1 == x2) {
            res.push_back({x1, square1[1]});
            res.push_back({x1, square2[1]});
            res.push_back({x1, square1[1] + square1[2]});
            res.push_back({x1, square2[1] + square2[2]});
        } else if (y1 == y2) {
            res.push_back({square1[0], y1});
            res.push_back({square2[0], y1});
            res.push_back({square1[0]+square1[2], y1});
            res.push_back({square2[0]+square2[2], y1});
        } else {
            // 直线方程f(y)
            auto fy = [=](double y) -> double {
                const double k = (x2 - x1) / (y2 - y1);
                return k * (y - y1) + x1;
            };
            // 直线方程f(x)
            auto fx = [=](double x) -> double {
                const double k = (y2 - y1) / (x2 - x1);
                return k * (x - x1) + y1;
            };
            for (auto &sq : {square1, square2}) {
                for (auto &p : vector<pair<double, double> >{
                    {fy(sq[1]), sq[1]},
                    {fy(sq[1]+sq[2]), sq[1]+sq[2]},
                    {sq[0], fx(sq[0])},
                    {sq[0]+sq[2], fx(sq[0]+sq[2])}})
                {
                    // 判断候选顶点是否在正方形中
                    if (p.first >= sq[0] && p.first <= sq[0] + sq[2]) {
                        if (p.second >= sq[1] && p.second <= sq[1] + sq[2]) {
                            res.push_back(p);
                        }
                    }
                }
            }
        }
        // 对顶点集排序
        sort(res.begin(), res.end());
        // 所求顶点为排序后的`res`数组的第一个顶点和最后一个顶点。
        return {
            res.front().first,
            res.front().second,
            res.back().first,
            res.back().second,
        };
    }
};