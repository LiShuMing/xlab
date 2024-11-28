
#include <gtest/gtest.h>
#include "common/consistent_hash.h"

#include <array>
#include <chrono>
#include <iostream>
#include <mutex>
#include <random>
#include <thread>
#include <vector>
#include <xmmintrin.h> // Include for _mm_pause

using namespace std;

class ConsistentHashTest : public testing::Test {};

TEST_F(ConsistentHashTest, TestBasic) {
    {
        ConsistentHash ch(1);
        ch.Initialize();
        std::string label = "1 virtualNodeNum";
        ch.StatisticPerf(label, 0, 65536);
    }

    {
        ConsistentHash ch2(32);
        ch2.Initialize();
        {
            std::string label2 = "32 virtualNodeNum";
            ch2.StatisticPerf(label2, 0, 65536);
        }
        {
            std::string label2 = "32 virtualNodeNum(delete one node)";
            ch2.DeletePhysicalNode("192.168.1.101");
            ch2.StatisticPerf(label2, 0, 65536);
        }
        {
            std::string label2 = "32 virtualNodeNum(add one node)";
            ch2.AddNewPhysicalNode("192.168.1.105");
            ch2.StatisticPerf(label2, 0, 65536);
        }
    }
}