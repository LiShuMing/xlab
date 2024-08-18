
#include <vector>
#include <utility>
#include <set>

#include <gtest/gtest.h>

using namespace std;

class Interview2Test : public testing::Test {};

/**
 * Compare two RLE encoded strings.
 */
int compare_rle(const string &a, const string &b) {
    int i = 0, j = 0;
    while (i < a.size() && j < b.size()) {
        if (a[i] != b[j]) {
            return -1;
        }
        i++;
        j++;
        int count_a = 0;
        while (i < a.size() && isdigit(a[i])) {
            count_a = count_a * 10 + a[i] - '0';
            i++;
        }
        int count_b = 0;
        while (j < b.size() && isdigit(b[j])) {
            count_b = count_b * 10 + b[j] - '0';
            j++;
        }
        if (count_a != count_b) {
            return -1;
        }
    }
    if (i < a.size() || j < b.size()) {
        return -1;
    }
    return 0;
}

TEST_F(Interview2Test, Test1) {
    string a = "a3b2c1";
    string b = "a3b2c1";
    EXPECT_EQ(compare_rle(a, b), 0);
}

