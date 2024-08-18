#include <iostream>
#include <string>
#include <random>

#include "gtest/gtest.h"
#include "tinykv/common/slice.hpp"
#include "tinykv/memtable/arena.hpp"
#include "tinykv/memtable/skiplist.hpp"

namespace tinykv {
namespace {

// Simple comparator for std::string
struct StringComparator : public Comparator<std::string> {
    auto Compare(const std::string& a, const std::string& b) const -> int override {
        int result = (a < b) ? -1 : (a > b) ? 1 : 0;
        std::cerr << "Compare: '" << a << "' vs '" << b << "' = " << result << std::endl;
        return result;
    }
};

// SkipList test with real SkipList
class SkipListTest : public testing::Test {
protected:
    void SetUp() override {
        arena_ = std::make_unique<Arena>();
        comparator_ = std::make_unique<StringComparator>();
        list_ = std::make_unique<SkipList<std::string, std::string>>(
            comparator_.get(), arena_.get(), 42);
    }

    std::unique_ptr<StringComparator> comparator_;
    std::unique_ptr<Arena> arena_;
    std::unique_ptr<SkipList<std::string, std::string>> list_;
};

// Basic insert and get
TEST_F(SkipListTest, InsertAndGet) {
    EXPECT_TRUE(list_->Empty());
    EXPECT_EQ(list_->Size(), 0);

    list_->Insert("key1", "value1");
    EXPECT_EQ(list_->Size(), 1);

    list_->Insert("key2", "value2");
    EXPECT_EQ(list_->Size(), 2);

    list_->Insert("key3", "value3");
    EXPECT_EQ(list_->Size(), 3);

    EXPECT_FALSE(list_->Empty());

    std::string value;
    std::cerr << "=== Getting key1 ===" << std::endl;
    bool found1 = list_->Get("key1", &value);
    std::cerr << "Get key1: " << found1 << std::endl;
    EXPECT_TRUE(found1);
    EXPECT_EQ(value, "value1");

    std::cerr << "=== Getting key2 ===" << std::endl;
    bool found2 = list_->Get("key2", &value);
    std::cerr << "Get key2: " << found2 << std::endl;
    EXPECT_TRUE(found2);
    EXPECT_EQ(value, "value2");

    std::cerr << "=== Getting key3 ===" << std::endl;
    bool found3 = list_->Get("key3", &value);
    std::cerr << "Get key3: " << found3 << std::endl;
    EXPECT_TRUE(found3);
    EXPECT_EQ(value, "value3");
}

}  // namespace
}  // namespace tinykv
