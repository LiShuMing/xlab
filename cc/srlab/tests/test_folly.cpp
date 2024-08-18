#include <gtest/gtest.h>
#include <folly/FBString.h>
#include <folly/String.h>
#include <folly/Conv.h>
#include <folly/container/F14Map.h>
#include <vector>
#include <string>

TEST(FollyStringTest, FBStringBasic)
{
    folly::fbstring str = "Hello Folly";
    EXPECT_EQ(str.size(), 11);
    EXPECT_EQ(str, "Hello Folly");
}

TEST(FollyStringTest, JoinStrings)
{
    std::vector<std::string> words{"folly", "is", "awesome"};
    folly::fbstring result = folly::join("-", words);
    EXPECT_EQ(result, "folly-is-awesome");
}

TEST(FollyStringTest, SplitStrings)
{
    std::string input = "one,two,three";
    std::vector<folly::fbstring> tokens;
    folly::split(',', input, tokens);
    
    ASSERT_EQ(tokens.size(), 3);
    EXPECT_EQ(tokens[0], "one");
    EXPECT_EQ(tokens[1], "two");
    EXPECT_EQ(tokens[2], "three");
}

TEST(FollyConvTest, ToConversion)
{
    int num = 42;
    std::string str = folly::to<std::string>(num);
    EXPECT_EQ(str, "42");
    
    double d = folly::to<double>("3.14");
    EXPECT_NEAR(d, 3.14, 0.001);
}

TEST(FollyContainerTest, F14Map)
{
    folly::F14FastMap<std::string, int> map;
    map["one"] = 1;
    map["two"] = 2;
    map["three"] = 3;
    
    EXPECT_EQ(map.size(), 3);
    EXPECT_EQ(map["one"], 1);
    EXPECT_EQ(map["two"], 2);
    EXPECT_TRUE(map.find("four") == map.end());
}

#ifdef SRLAB_NEEDS_GTEST_MAIN
int main(int argc, char** argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
#endif

