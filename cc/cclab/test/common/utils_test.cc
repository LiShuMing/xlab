#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <string>
#include <shared_mutex>
#include <vector>
#include <memory>
#include <ranges>
#include <numeric> 
#include <algorithm> // new fold_left, ends_with
#include <string>
#include <cctype>
#include <functional>

#include "absl/container/flat_hash_set.h"
#include "absl/container/flat_hash_map.h"
#include "absl/container/node_hash_map.h"

using namespace std;

namespace test {

// Basic Test
class UtilsTest : public testing::Test {};

using namespace std;

struct VectorCompare {
    bool operator()(const std::vector<std::string>& a, const std::vector<std::string>& b) const {
        if (a.size() != b.size()) {
            return a.size() < b.size();
        }
        for (size_t i = 0; i < a.size(); ++i) {
            if (a[i] != b[i]) {
                return a[i] < b[i];
            }
        }
        return false;
    }
};

struct CaseInsensitiveVectorCompare {
    static bool caseInsensitiveCompare(const std::string& a, const std::string& b) {
        return std::lexicographical_compare(
            a.begin(), a.end(),
            b.begin(), b.end(),
            [](unsigned char c1, unsigned char c2) {
                return std::tolower(c1) < std::tolower(c2);
            }
        );
    }

    bool operator()(const std::vector<std::string>& a, const std::vector<std::string>& b) const {
        if (a.size() != b.size()) {
            return a.size() < b.size();
        }
        for (size_t i = 0; i < a.size(); ++i) {
            if (!caseInsensitiveCompare(a[i], b[i]) && !caseInsensitiveCompare(b[i], a[i])) {
                continue; 
            }
            return caseInsensitiveCompare(a[i], b[i]); 
        }
        return false;
    }
};

struct VectorCompare2 {
    bool caseInsensitiveEqual(const std::string& lhs, const std::string& rhs) const {
        if (lhs.size() != rhs.size()) {
            return false;
        }
        return strncasecmp(lhs.c_str(), rhs.c_str(), lhs.size()) == 0;
    }

    bool caseInsensitiveLess(const std::string& lhs, const std::string& rhs) const {
        return strncasecmp(lhs.c_str(), rhs.c_str(), std::min(lhs.size(), rhs.size())) < 0;
    }

    bool operator()(const std::vector<std::string>& a, const std::vector<std::string>& b) const {
        if (a.size() != b.size()) {
            return a.size() < b.size();
        }

        for (size_t i = 0; i < a.size(); ++i) {
            if (caseInsensitiveEqual(a[i], b[i])) {
                continue; 
            }
            return caseInsensitiveLess(a[i], b[i]);
        }

        return false; 
    }
};

struct StringCaseEqual {
public:
    bool operator()(const std::string& lhs, const std::string& rhs) const {
        if (lhs.size() != rhs.size()) {
            return false;
        }
        return strncasecmp(lhs.c_str(), rhs.c_str(), 0) == 0;
    }
};

struct StringCaseLess {
public:
    bool operator()(const std::string& lhs, const std::string& rhs) const {
        size_t common_size = std::min(lhs.size(), rhs.size());
        auto cmp = strncasecmp(lhs.c_str(), rhs.c_str(), common_size);
        if (cmp == 0) {
            return lhs.size() < rhs.size();
        }
        return cmp < 0;
    }
};

struct VectorCompare3 {
    bool operator()(const std::vector<std::string>& a, const std::vector<std::string>& b) const {
        if (a.size() != b.size()) {
            return a.size() < b.size();
        }

        for (size_t i = 0; i < a.size(); ++i) {
            if (_eq(a[i], b[i])) {
                continue; 
            }
            return _less(a[i], b[i]);
        }

        return false; 
    }

private:
    StringCaseEqual _eq;
    StringCaseLess _less;
};
TEST_F(UtilsTest, TestMap1) {
    std::map<std::vector<std::string>, int, VectorCompare> vecMap;

    vecMap[{"apple", "banana"}] = 1;
    vecMap[{"banana"}] = 2;
    vecMap[{"apple", "apple"}] = 3;

    for (const auto &[key, value] : vecMap) {
        for (const auto &str : key) {
            std::cout << str << " ";
        }
        std::cout << ": " << value << std::endl;
    }
}

TEST_F(UtilsTest, TestSet1) {
    std::set<std::vector<std::string>, VectorCompare> s;

    s.insert({"apple", "banana"});
    s.insert({"banana"});
    s.insert({"Banana"});
    s.insert({"BananA"});
    s.insert({"banana"});
    s.insert({"apple", "apple"});
    for (auto& key : s) {
        for (const auto &str : key) {
            std::cout << str << " ";
        }
        std::cout << std::endl;
    }
}

TEST_F(UtilsTest, TestSet2) {
    std::set<std::vector<std::string>, CaseInsensitiveVectorCompare> s;

    s.insert({"apple", "banana"});
    s.insert({"banana"});
    s.insert({"Banana"});
    s.insert({"BananA"});
    s.insert({"banana"});
    s.insert({"apple", "apple"});
    for (auto& key : s) {
        for (const auto &str : key) {
            std::cout << str << " ";
        }
        std::cout << std::endl;
    }
}

TEST_F(UtilsTest, TestSet3) {
    std::set<std::vector<std::string>, VectorCompare2> s;

    s.insert({"apple", "banana"});
    s.insert({"banana"});
    s.insert({"Banana"});
    s.insert({"BananA"});
    s.insert({"banana"});
    s.insert({"apple", "apple"});
    for (auto& key : s) {
        for (const auto &str : key) {
            std::cout << str << " ";
        }
        std::cout << std::endl;
    }
}

TEST_F(UtilsTest, TestSet4) {
    std::set<std::vector<std::string>, VectorCompare3> s;

    s.insert({"apple", "banana"});
    s.insert({"banana"});
    s.insert({"Banana"});
    s.insert({"BananA"});
    s.insert({"banana"});
    s.insert({"apple", "apple"});
    for (auto& key : s) {
        for (const auto &str : key) {
            std::cout << str << " ";
        }
        std::cout << std::endl;
    }
}


template <bool is_case_sensitive>
class ConditionalComparator {
public:
    // ConditionalComparator() : case_sensitive_(false) {}
    // ConditionalComparator(bool case_sensitive) : case_sensitive_(case_sensitive) {}
    bool operator()(const std::string& lhs, const std::string& rhs) const {
        if constexpr (is_case_sensitive) {
            return lhs < rhs;
        } else {
            return toLower(lhs) < toLower(rhs);
        }
    }

private:
    static std::string toLower(const std::string& str) {
        std::string lower_str;
        for (char c : str) {
            lower_str.push_back(std::tolower(c));
        }
        return lower_str;
    }
};

TEST_F(UtilsTest, CmpTest1) {
    bool case_sensitive = false;
    // std::map<std::string, int, ConditionalComparator> myMap(ConditionalComparator(case_sensitive));
    std::map<std::string, int, ConditionalComparator<false>> myMap;

    myMap.insert({"Apple", 1});
    myMap.insert({"apple", 2});
    for (const auto &[key, value] : myMap) {
        std::cout << key << ": " << value << std::endl;
    }
}

TEST_F(UtilsTest, CmpTest2) {
    bool case_sensitive = false;
    auto comparator = [case_sensitive](const std::string& lhs, const std::string& rhs) {
        if (case_sensitive) {
            return lhs < rhs;
        } else {
            auto toLower = [](const std::string& str) {
                std::string lower_str;
                for (char c : str) {
                    lower_str.push_back(std::tolower(c));
                }
                return lower_str;
            };
            return toLower(lhs) < toLower(rhs);
        }
    };
    std::map<std::string, int, decltype(comparator)> myMap(comparator);
    myMap["Apple"] = 1;
    myMap["apple"] = 2;
    for (const auto& [key, value] : myMap) {
        std::cout << key << ": " << value << std::endl;
    }
}

TEST_F(UtilsTest, CmpTest3) {
    bool case_sensitive = false;
    std::function<bool(const std::string&, const std::string&)> comparator;

    if (case_sensitive) {
        comparator = [](const std::string& lhs, const std::string& rhs) {
            return lhs < rhs;
        };
    } else {
        comparator = [](const std::string& lhs, const std::string& rhs) {
            auto toLower = [](const std::string& str) {
                std::string lower_str;
                for (char c : str) {
                    lower_str.push_back(std::tolower(c));
                }
                return lower_str;
            };
            return toLower(lhs) < toLower(rhs);
        };
    }

    std::map<std::string, int, decltype(comparator)> myMap(comparator);

    myMap["Apple"] = 1;
    myMap["apple"] = 2;

    for (const auto& [key, value] : myMap) {
        std::cout << key << ": " << value << std::endl;
    }

}


} // namespace test
