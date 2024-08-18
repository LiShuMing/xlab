#include <iostream>
#include <chrono>

using namespace std;
using namespace std::chrono;

milliseconds test_duration(volatile int * ptr)  // 使用volatile指针防止编译器的优化
{
    auto start = steady_clock::now();
    for (unsigned i = 0; i < 100'000'000; ++i)
    {
        ++(*ptr);
    }
    auto end = steady_clock::now();
    return duration_cast<milliseconds>(end - start);
}

//int main()
//{
//    int raw[2] = {0, 0};
//    {
//        int* ptr = raw;
//
//        cout << "address of aligned pointer: " << (void*)ptr << endl;
//        cout << "aligned access: " << test_duration(ptr).count() << "ms" << endl;
//        *ptr = 0;
//    }
//    {
//        int* ptr = (int*)(((char*)raw) + 1);
//        cout << "address of unaligned pointer: " << (void*)ptr << endl;
//        cout << "unaligned access: " << test_duration(ptr).count() << "ms" << endl;
//        *ptr = 0;
//    }
//    cin.get();
//    return 0;
//}
