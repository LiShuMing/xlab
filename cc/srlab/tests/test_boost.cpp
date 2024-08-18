#include <gtest/gtest.h>
#include <boost/algorithm/string.hpp>
#include <boost/filesystem.hpp>
#include <string>
#include <vector>

TEST(BoostAlgorithmTest, StringJoin)
{
    std::vector<std::string> words{"boost", "test", "example"};
    std::string result = boost::algorithm::join(words, "-");
    EXPECT_EQ(result, "boost-test-example");
}

TEST(BoostAlgorithmTest, StringSplit)
{
    std::string input = "one,two,three";
    std::vector<std::string> tokens;
    boost::algorithm::split(tokens, input, boost::algorithm::is_any_of(","));
    
    ASSERT_EQ(tokens.size(), 3);
    EXPECT_EQ(tokens[0], "one");
    EXPECT_EQ(tokens[1], "two");
    EXPECT_EQ(tokens[2], "three");
}

TEST(BoostAlgorithmTest, ToUpper)
{
    std::string text = "hello world";
    boost::algorithm::to_upper(text);
    EXPECT_EQ(text, "HELLO WORLD");
}

TEST(BoostFilesystemTest, CurrentPath)
{
    boost::filesystem::path current = boost::filesystem::current_path();
    EXPECT_FALSE(current.empty());
    EXPECT_TRUE(boost::filesystem::exists(current));
}

TEST(BoostFilesystemTest, PathOperations)
{
    boost::filesystem::path p("/usr/local/bin");
    EXPECT_EQ(p.parent_path().string(), "/usr/local");
    EXPECT_EQ(p.filename().string(), "bin");
}

#ifdef SRLAB_NEEDS_GTEST_MAIN
int main(int argc, char** argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
#endif

