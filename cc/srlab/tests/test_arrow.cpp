#include <arrow/api.h>
#include <gtest/gtest.h>

TEST(ArrowArrayTest, BuildsExpectedArray)
{
    arrow::Int32Builder builder;
    auto status = builder.AppendValues({1, 2, 3, 4});
    ASSERT_TRUE(status.ok()) << "AppendValues failed: " << status.ToString();

    std::shared_ptr<arrow::Array> array;
    status = builder.Finish(&array);
    ASSERT_TRUE(status.ok()) << "Finish failed: " << status.ToString();

    ASSERT_NE(array, nullptr);
    EXPECT_EQ(array->length(), 4);
    EXPECT_TRUE(array->IsValid(0));
    EXPECT_TRUE(array->IsValid(3));

    auto int32_array = std::static_pointer_cast<arrow::Int32Array>(array);
    EXPECT_EQ(int32_array->Value(0), 1);
    EXPECT_EQ(int32_array->Value(3), 4);
}

#ifdef SRLAB_NEEDS_GTEST_MAIN
int main(int argc, char** argv)
{
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
#endif

