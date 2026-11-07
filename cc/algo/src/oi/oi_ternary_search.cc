/**
 * 三分求单峰极值
 * 例题：洛谷 P3382 【模板】三分法
 *       https://www.luogu.com.cn/problem/P3382
 *       给一个 n 次多项式，保证在 [l, r] 上存在唯一极大值点，求它。
 *
 * 做法：取两个三等分点 left_mid、right_mid，比较 f(left_mid) 与 f(right_mid)：
 *   f(left_mid) <  f(right_mid) -> 峰在 left_mid 右侧，丢左三分之一
 *   f(left_mid) >  f(right_mid) -> 峰在 right_mid 左侧，丢右三分之一
 *   f(left_mid) == f(right_mid) -> 严格单峰时峰被夹在两点之间，两侧都丢
 * 每轮区间缩到 2/3，迭代 100 轮即 6e-18 倍，远低于 double 精度。
 *
 * 前提是「严格单峰」：先单调升、后单调降。这条前提在整数序列上最容易被破坏，
 * 坡上出现平台时三分会把真峰丢掉：
 *   序列 {2,1,1,1,0}，m1 = 1 与 m2 = 3 取值都是 1，等号分支判「峰在 [1,3]」，
 *   真正的峰在下标 0 被砍掉了。
 * 平台的出路是线性扫「最后一个满足 a[i] < a[i+1] 的下标 i，i + 1 即峰」，对任意
 * 「先非降、后非增」的序列都成立，代价 O(n)。想回到 O(log n) 必须让这个谓词单调，
 * 也就是要求平台只能出现在峰顶、两侧严格；坡中有平台时（[1,1,2,2,3,3] 上该谓词是
 * 「假-真-假-真-假」）任何相邻比较的二分都会失效。
 *
 * 另一个必须注意的点：三分不需要导数，但导数能更好地利用信息；f' 左正右负，
 * 对 f' 二分是 O(log) 且精度更高，本文件用它做交叉验证。
 */

#include "../include/fwd.h"

#include <cmath>
#include <cstdlib>
#include <iomanip>
#include <random>

namespace {

// (2/3)^100 ≈ 2.5e-18，低于 double 有效精度，只是安全上限
constexpr int kTernaryIterations = 100;
// 导函数二分 200 轮：区间乘 2^-200
constexpr int kBisectionIterations = 200;
// 网格基线每侧的采样段数
constexpr int kGridSegments = 200000;
// 随机对拍轮数
constexpr int kRandomRounds = 200;
constexpr int kIntegerRounds = 2000;

// Horner 求值，coefficients[0] 是最高次项，O(n)
double EvaluatePolynomial(const std::vector<double>& coefficients, double x) {
    double value = 0.0;
    for (double coefficient : coefficients) value = value * x + coefficient;
    return value;
}

// f' 的系数是 coefficients[i] * (n - i)，同样用 Horner
double EvaluateDerivative(const std::vector<double>& coefficients, double x) {
    const int degree = static_cast<int>(coefficients.size()) - 1;
    double value = 0.0;
    for (int i = 0; i < degree; ++i) {
        value = value * x + coefficients[i] * (degree - i);
    }
    return value;
}

// 三分：返回 [left, right] 内的极大值点
double TernaryPeakX(const std::vector<double>& coefficients, double left, double right) {
    for (int iteration = 0; iteration < kTernaryIterations; ++iteration) {
        const double third = (right - left) / 3.0;
        const double left_mid = left + third;
        const double right_mid = right - third;
        const double left_value = EvaluatePolynomial(coefficients, left_mid);
        const double right_value = EvaluatePolynomial(coefficients, right_mid);
        if (left_value < right_value) {
            left = left_mid;
        } else if (left_value > right_value) {
            right = right_mid;
        } else {
            left = left_mid;
            right = right_mid;
        }
    }
    return (left + right) / 2.0;
}

// 对照解法：f' 左正右负，对导函数二分
double BisectDerivativePeakX(const std::vector<double>& coefficients, double left, double right) {
    for (int iteration = 0; iteration < kBisectionIterations; ++iteration) {
        const double mid = left + (right - left) / 2.0;
        if (EvaluateDerivative(coefficients, mid) > 0.0) {
            left = mid;
        } else {
            right = mid;
        }
    }
    return (left + right) / 2.0;
}

// 独立基线：稠密网格扫描，既不用三分也不用导数
double GridPeakX(const std::vector<double>& coefficients, double left, double right, int segments) {
    int best_index = 0;
    double best_value = EvaluatePolynomial(coefficients, left);
    for (int i = 1; i <= segments; ++i) {
        const double x = left + (right - left) * i / segments;
        const double value = EvaluatePolynomial(coefficients, x);
        if (value > best_value) {
            best_value = value;
            best_index = i;
        }
    }
    return left + (right - left) * best_index / segments;
}

// 整数三分：要求严格单峰。收尾留四点线性扫，因为 l + 1 == r 时三等分点会原地打转
int IntegerPeakIndex(const std::vector<long long>& values) {
    int left = 0;
    int right = static_cast<int>(values.size()) - 1;
    while (right - left > 3) {
        const int third = (right - left) / 3;
        const int left_mid = left + third;
        const int right_mid = right - third;
        if (values[left_mid] < values[right_mid]) {
            left = left_mid + 1;
        } else if (values[left_mid] > values[right_mid]) {
            right = right_mid - 1;
        } else {
            left = left_mid;
            right = right_mid;
        }
    }
    int best = left;
    for (int i = left + 1; i <= right; ++i) {
        if (values[i] > values[best]) best = i;
    }
    return best;
}

// 线性版：最后一个上升点的右邻即峰。对任意「先非降、后非增」的序列都成立
int PeakIndexByLastRise(const std::vector<long long>& values) {
    int peak = 0;
    const int last = static_cast<int>(values.size()) - 1;
    for (int i = 0; i < last; ++i) {
        if (values[i] < values[i + 1]) peak = i + 1;
    }
    return peak;
}

// 二分版：平台只在峰顶、两侧严格时，「a[i] < a[i+1]」才单调，才能丢掉一半
int PeakIndexByBisection(const std::vector<long long>& values) {
    int last_rise = -1;
    int low = 0;
    int high = static_cast<int>(values.size()) - 2;
    while (low <= high) {
        const int mid = low + (high - low) / 2;
        if (values[mid] < values[mid + 1]) {
            last_rise = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return last_rise < 0 ? 0 : last_rise + 1;
}

// 线性扫描基线：返回第一个最大值下标
int BrutePeakIndex(const std::vector<long long>& values) {
    return static_cast<int>(std::max_element(values.begin(), values.end()) - values.begin());
}

// 一组多项式用例：三分与导函数二分都要命中解析峰点，网格基线也要落在同一格
void CheckPolynomial(const char* name, const std::vector<double>& coefficients, double left,
                     double right, double expected_peak) {
    const double ternary_peak = TernaryPeakX(coefficients, left, right);
    const double derivative_peak = BisectDerivativePeakX(coefficients, left, right);
    const double grid_peak = GridPeakX(coefficients, left, right, kGridSegments);
    const double step = (right - left) / kGridSegments;
    std::cout << std::left << std::setw(28) << name << "三分 = " << std::setprecision(9)
              << ternary_peak << "，导数二分 = " << derivative_peak << "，网格 = " << grid_peak
              << "（解析峰 " << expected_peak << "）" << std::endl;
    if (std::fabs(ternary_peak - expected_peak) > 1e-6) std::abort();
    if (std::fabs(derivative_peak - expected_peak) > 1e-6) std::abort();
    if (std::fabs(grid_peak - expected_peak) > 2.0 * step) std::abort();
}

// 由导数 -(x - c)(x^2 + p^2) 积分得到严格单峰四次多项式，峰点解析为 c
std::vector<double> MakeUnimodalQuartic(double peak_x, double curvature) {
    const double square = curvature * curvature;
    return {-0.25, peak_x / 3.0, -square / 2.0, peak_x * square, 0.0};
}

}  // namespace

int main() {
    std::cout << std::fixed << std::setprecision(9);

    // 1) 固定用例：每一组的峰点都能由 f' = 0 手算出来
    //    x^3 - 6x^2 + 9x 的 f' = 3(x-1)(x-3)，[0, 2] 上峰在 1
    CheckPolynomial("cubic peak 1", {1.0, -6.0, 9.0, 0.0}, 0.0, 2.0, 1.0);
    //    -2x^3 + 3x^2 + 12x 的 f' = -6(x-2)(x+1)，[0, 4] 上峰在 2
    CheckPolynomial("cubic peak 2", {-2.0, 3.0, 12.0, 0.0}, 0.0, 4.0, 2.0);
    //    -(x-1)(x^2+1) 积分出的非对称四次多项式，峰在 1
    CheckPolynomial("quartic peak 1", MakeUnimodalQuartic(1.0, 1.0), 0.0, 3.0, 1.0);
    //    负峰点，峰在 -2
    CheckPolynomial("quartic peak -2", MakeUnimodalQuartic(-2.0, 0.5), -5.0, 0.0, -2.0);
    //    峰点贴左端：区间 [0, 0.5] 内峰在 0.1
    CheckPolynomial("quartic peak 0.1", MakeUnimodalQuartic(0.1, 1.5), 0.0, 0.5, 0.1);

    // 2) 窄区间：区间宽 1e-9，峰在 1.5e-9。迭代次数固定，不会因区间过窄死循环
    {
        const std::vector<double> coefficients = MakeUnimodalQuartic(1.5e-9, 1.0);
        const double peak = TernaryPeakX(coefficients, 1e-9, 2e-9);
        std::cout << std::left << std::setw(28) << "narrow interval" << "三分 = "
                  << std::setprecision(15) << peak << "（解析峰 1.5e-09）" << std::endl;
        std::cout << std::setprecision(9);
        if (std::fabs(peak - 1.5e-9) > 1e-12) std::abort();
    }

    // 3) 随机对拍：随机峰点与曲率的四次多项式，非对称，峰点解析已知
    std::mt19937 random_engine(20261107);
    std::uniform_real_distribution<double> peak_distribution(-4.0, 4.0);
    std::uniform_real_distribution<double> curvature_distribution(0.3, 2.0);
    std::uniform_real_distribution<double> width_distribution(0.2, 3.0);
    for (int round = 0; round < kRandomRounds; ++round) {
        const double peak_x = peak_distribution(random_engine);
        const std::vector<double> coefficients =
            MakeUnimodalQuartic(peak_x, curvature_distribution(random_engine));
        const double left = peak_x - width_distribution(random_engine);
        const double right = peak_x + width_distribution(random_engine);
        const double got = TernaryPeakX(coefficients, left, right);
        const double derivative_got = BisectDerivativePeakX(coefficients, left, right);
        if (std::fabs(got - peak_x) > 1e-6 || std::fabs(derivative_got - peak_x) > 1e-6) {
            std::cout << "FAIL: round " << round << " peak=" << peak_x << " ternary=" << got
                      << " derivative=" << derivative_got << std::endl;
            std::abort();
        }
    }
    std::cout << std::left << std::setw(28) << "random quartics"
              << kRandomRounds << " 组：三分与导数二分都命中解析峰点" << std::endl;

    // 4) 整数三分：严格单峰的随机序列，与线性扫描对拍
    for (int round = 0; round < kIntegerRounds; ++round) {
        const int length = 1 + static_cast<int>(random_engine() % 40);
        const int peak = static_cast<int>(random_engine() % length);
        std::vector<long long> values(length);
        values[0] = static_cast<long long>(random_engine() % 5);
        for (int i = 0; i + 1 < length; ++i) {
            const long long step = 1 + static_cast<long long>(random_engine() % 2);
            values[i + 1] = values[i] + (i < peak ? step : -step);
        }
        const int got = IntegerPeakIndex(values);
        const int want = BrutePeakIndex(values);
        if (got != want) {
            std::cout << "FAIL: integer round " << round << " length=" << length
                      << " got=" << got << " want=" << want << std::endl;
            std::abort();
        }
    }
    std::cout << std::left << std::setw(28) << "strict unimodal ints"
              << kIntegerRounds << " 组：整数三分与线性扫描一致" << std::endl;

    // 5) 平台反例：三分丢掉真峰，线性「最后上升点」仍然正确
    {
        const std::vector<long long> values = {2, 1, 1, 1, 0};
        const int ternary_got = IntegerPeakIndex(values);
        const int linear_got = PeakIndexByLastRise(values);
        std::cout << std::left << std::setw(28) << "plateau counterexample"
                  << "三分给出下标 " << ternary_got << "（值 " << values[ternary_got]
                  << "），线性给出下标 " << linear_got << "（值 " << values[linear_got] << "）"
                  << std::endl;
        // 只锁正确解法，不把三分的已知缺陷写死
        if (linear_got != BrutePeakIndex(values)) std::abort();
    }

    // 6) 含平台的随机序列：线性「最后上升点」与「第一个最大值下标」一致
    for (int round = 0; round < kIntegerRounds; ++round) {
        const int length = 1 + static_cast<int>(random_engine() % 40);
        const int peak = static_cast<int>(random_engine() % length);
        std::vector<long long> values(length);
        values[0] = static_cast<long long>(random_engine() % 5);
        for (int i = 0; i + 1 < length; ++i) {
            const long long step = static_cast<long long>(random_engine() % 3);  // 允许 0
            values[i + 1] = values[i] + (i < peak ? step : -step);
        }
        const int got = PeakIndexByLastRise(values);
        const int want = BrutePeakIndex(values);
        if (got != want) {
            std::cout << "FAIL: plateau round " << round << " length=" << length
                      << " got=" << got << " want=" << want << std::endl;
            std::abort();
        }
    }
    std::cout << std::left << std::setw(28) << "plateau ints" << kIntegerRounds
              << " 组：线性最后上升点与线性扫描一致" << std::endl;

    // 7) 平台只在峰顶、两侧严格：谓词单调，二分可以 O(log n) 命中
    for (int round = 0; round < kIntegerRounds; ++round) {
        const int length = 1 + static_cast<int>(random_engine() % 40);
        const int plateau_start = static_cast<int>(random_engine() % length);
        const int plateau_end =
            plateau_start + static_cast<int>(random_engine() % (length - plateau_start));
        std::vector<long long> values(length);
        values[0] = static_cast<long long>(random_engine() % 5);
        for (int i = 0; i + 1 < length; ++i) {
            const long long rise = 1 + static_cast<long long>(random_engine() % 2);
            if (i + 1 <= plateau_start) {
                values[i + 1] = values[i] + rise;
            } else if (i + 1 <= plateau_end) {
                values[i + 1] = values[i];
            } else {
                values[i + 1] = values[i] - rise;
            }
        }
        const int got = PeakIndexByBisection(values);
        const int want = BrutePeakIndex(values);
        if (got != want) {
            std::cout << "FAIL: top plateau round " << round << " length=" << length
                      << " plateau=[" << plateau_start << "," << plateau_end
                      << "] got=" << got << " want=" << want << std::endl;
            std::abort();
        }
    }
    std::cout << std::left << std::setw(28) << "top plateau ints" << kIntegerRounds
              << " 组：二分与线性扫描一致" << std::endl;

    std::cout << "oi_ternary_search: all checks passed" << std::endl;
    return 0;
}
