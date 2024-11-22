#include <gtest/gtest.h>

#include <atomic>
#include <cassert>
#include <cstring>
#include <functional>
#include <iostream>
#include <thread>
#include <vector>

#include "common/coroutine.h"

// Thread Test
class CoroutineTest : public testing::Test {
};

int ascending (ccrContParam) {
    ccrBeginContext;
    int i;
    ccrEndContext(foo);

    ccrBegin(foo);
    for (foo->i = 0; foo->i < 10; foo->i++) {
        ccrReturn(foo->i);
    }
    ccrFinish(-1);
}

int ascending(void) {
    static int i;

    scrBegin;
    for (i = 0; i < 10; i++) {
        scrReturn(i);
    }
    scrFinish(-1);
}

TEST_F(CoroutineTest, TestAscendingWithStatic) {
    ccrContext z = 0;
    do {
        printf("got number %d\n", ascending(&z));
    } while (z);
}


TEST_F(CoroutineTest, TestAscendingWithReeenrant) {
    ccrContext z = 0;
    do {
        printf("got number %d\n", ascending(&z));
    } while (z);
}

int main(int argc, char** argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}