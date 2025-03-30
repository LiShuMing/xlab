#include <gtest/gtest.h>

#include <iostream>
#include <chrono>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <mutex>
#include <set>
#include <thread>
#include <bitset>
#include <vector>
#include <map>
#include <unordered_map>

#include <immintrin.h>
#include <x86intrin.h>


namespace test {

using namespace std;
using namespace std::chrono;

class DataTest : public testing::Test {};

#define N_THREAD 1000

// https://stackoverflow.com/questions/63584337/do-i-need-an-atomic-if-a-value-is-only-written
//
// According to §5.1.2.4 ¶25 and ¶4 of the ISO C11 standard, two different threads writing to the same memory location
// using non-atomic operations in an unordered fashion causes undefined behavior. The ISO C standard makes no exception
// to this rule if all threads are writing the same value.
//

//atomic<int> a{0};
int a{0};

void thread_f1() {
    for (int i = 0; i < 10; i++) {
        a++;
    }
    //std::this_thread::sleep_for(10ms);
}

void test_multi_threads_1() {
    /**
	for (int i=0; i < 100; i++) {
		cout<<"i:"<<i<<", popcount:"<<__builtin_popcount(i)<<endl;
	}*/

    vector<thread> ts(N_THREAD);
    for (int i=0; i<N_THREAD; i++) {
        //ts.emplace_back(std::thread(thread_f1));
        ts[i] = std::thread(thread_f1);
    }
    for (int i=0; i<N_THREAD; i++) {
        ts[i].join();
    }
    //cout<<"final sum:"<<a.load()<<endl;
    cout<<"final sum:"<<a<<endl;
}

int tab[5];
bool test_undefined_behavior_1(int v) {
    for (int i = 0; i  <= 5; i++) {
        if (tab[i] == v) return true;
    }
    return false;
}

template <typename T>
class ClassA {
public:
	ClassA(T a):_a(a){}
	T _a;
};


void test1() {
    for (int i = 0; i < 10; i++) {
        cout<<"test_undefined_behavior_1 i:"<<i<<", ans:"<<(test_undefined_behavior_1(i) ? "true" : "false")<<endl;
    }
}

void test2() {
	unordered_map<int, int> mp;
	mp[1] = 1;
	mp[2] = 1;
	mp[3] = 1;

	//abort();
	mp[3] = 1;

	// will abort
	// vector<int> a;
	// a.resize(0);
	// vector<int> *b;
	// b->swap(reinterpret_cast<vector<int>&>(a));

	for (auto&[k, v]: mp) {
		std::cout << "k:" << k << ", v:" << v<<std::endl;
	}
	mp.emplace(3, 2);
	for (auto&[k, v]: mp) {
		std::cout << "k:" << k << ", v:" << v<<std::endl;
	}
}

template<class T>
inline void print_mm256(__m256i& v) {
	const size_t n = sizeof(v) / sizeof(T);
	T buffer[n];
	_mm256_storeu_si256((__m256i*)buffer, v);
	for (int i = 0; i < n; i++) {
		//cout<<hex<<buffer[i]<<" ";
		cout<<bitset<sizeof(unsigned int)*8>(buffer[i])<<" ";
	}
	cout<<endl;
}

void test3() {
	__m256i t = _mm256_set_epi64x(1, 2, 3, 4);
	print_mm256<long>(t);
	//auto t1 = _mm256_set1_epi64x(0xBF);
	auto t1 = _mm256_set1_epi8(0xBF);
	print_mm256<long>(t1);

	vector<int> v1{1, 2, 3};
	vector<int> v2{1, 2, 3};
	vector<int> v3{1, 3, 2};
	cout <<"v1 ==v2:"<< (v1 == v2)<<std::endl;
	cout <<"v1 ==v3:"<< (v1 == v3)<<std::endl;
}

void test4() {
	uint8_t* a = new uint8_t[10];
	// uint8_t* b = a + 0;
	// uint8_t* c = a + 3;
	// uint8_t* d = a + 9;
	// delete b;
	// delete c;
	// delete d;
	delete[] a;
}

struct Data1 {
	vector<int> a;
};
struct Data2 {
	std::map<int, int> a;
};
void test5() {
	std::cout << "data1's size:" << sizeof(Data1) << std::endl;
	std::cout << "data2's size:" << sizeof(Data2) << std::endl;
	std::vector<int> a;
	std::cout << "vector's size:" << sizeof(std::vector<int>) << std::endl;

	std::map<int, int> m1;
	std::cout << "map's size:" << sizeof(std::map<int, int>) << std::endl;
	m1[0] = 1;
	m1[10] = 1;
	auto iter = m1.find(0);
	if (iter != m1.end()) {
		iter->second += 1;
		std::cout << "first:" <<  iter->first << ", value:" << iter->second << std::endl;
	}
	std::cout << "m1:" << m1[0];
}

template <typename T>
class A {
	public:
		A():is_a(false){}
		bool func_a() const {return is_a;}
	private:
	bool is_a{false};
};

template <typename T>
struct AA: A<T> {
	int a = 0;
};

template <typename T, typename Derived>
struct Base {

	void drived_func() {
		static_cast<Derived*>(this)->template func();
	}
	T a;
};

template <typename T>
struct D {

};
	
template <typename T>
struct D1: public D<T>, public Base<T, D1<T>> {
	void func() {
		std::cout << "D1 func" << std::endl;
	}
};

template <typename T>
struct DD1: public D<T>, public Base<T, DD1<T>> {
	void func() {
		std::cout << "DD1 func" << std::endl;
	}
};

void func(std::vector<int> a, int c) {
	auto aa = std::move(a);
	std::cout << "aa's size:" << aa.size() << ", c:" << c << std::endl;
}

// 使用volatile指针防止编译器的优化
milliseconds test_duration(volatile int *ptr) {
    auto start = steady_clock::now();
    for (unsigned i = 0; i < 100'000'000; ++i) {
        ++(*ptr);
    }
    auto end = steady_clock::now();
    return duration_cast<milliseconds>(end - start);
}

TEST_F(DataTest, TestBasic1) {
    int raw[2] = {0, 0};
    {
        int *ptr = raw;

        cout << "address of aligned pointer: " << (void *)ptr << endl;
        cout << "aligned access: " << test_duration(ptr).count() << "ms" << endl;
        *ptr = 0;
    }
    {
        int *ptr = (int *)(((char *)raw) + 1);
        cout << "address of unaligned pointer: " << (void *)ptr << endl;
        cout << "unaligned access: " << test_duration(ptr).count() << "ms" << endl;
        *ptr = 0;
    }
    cin.get();
}

TEST_F(DataTest, TestBasic2) {
	//test4();
	//test5();
	//AA<int> aa1;
	//std::cout<<"aa1:" << aa1.func_a()<<std::endl;

	//D1<int> d;
	//d.drived_func();
	//DD1<int> dd;
	//dd.drived_func();
	//
	std::vector<int> a{1, 2, 3};
	func(a, 1);
	func(a, 1);
	func(a, 1);
	func(a, 1);
	func(std::move(a), 1);
	func(std::move(a), 1);

	std::shared_ptr<int> sa = nullptr;
	std::cout<< "is null:"  << int(sa != nullptr);
	std::cout<< "is null:"  << int(sa == nullptr);

	sa = std::make_shared<int>(1);
	std::cout<< "is null:"  << int(sa != nullptr) << std::endl;;
	sa.reset();
	std::cout<< "is null:"  << int(sa != nullptr) << std::endl;;
	std::cout<< "is null:"  << int(!sa) << std::endl;;

	static auto ssa = std::make_shared<int>(1);
	auto ssa1 = std::move(ssa);
	std::cout<< "ssa is null:"  << int(ssa != nullptr) << std::endl;;
	auto ssa2 = std::move(ssa);
	std::cout<< "ssa is null:"  << int(ssa != nullptr) << std::endl;;
	ssa2.reset();
	std::cout<< "ssa is null:"  << int(ssa != nullptr) << std::endl;;

	test2();
}

} // namespace test