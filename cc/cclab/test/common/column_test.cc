#include <gtest/gtest.h>

#include <algorithm> // new fold_left, ends_with
#include <atomic>
#include <cctype>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <memory>
#include <numeric>
#include <queue>
#include <ranges>
#include <shared_mutex>
#include <string>
#include <vector>

#include "common/cow.h"

using namespace std;

namespace test {

// Basic Test
class ColumnTest : public testing::Test {};

using namespace std;

class IColumn : public COW<IColumn> {
  private:
    friend class COW<IColumn>;
    virtual MutablePtr deepMutate() const { return shallow_mutate(); }

  public:
    IColumn() {
        std::cerr << "IColumn constructor" << std::endl;
    }
    IColumn(const IColumn &) {
        std::cerr << "IColumn copy constructor" << std::endl;
    }
    virtual ~IColumn() = default;

    virtual MutablePtr clone() const = 0;
    virtual Ptr clone_shared() const = 0;
    virtual int get() const = 0;
    virtual void set(int value) = 0;

    // use reference to avoid copy
    static MutablePtr mutate(Ptr ptr) { return ptr->deepMutate(); }
    static MutablePtr cow(const Ptr& ptr) { return ptr->deepMutate(); }
};

using ColumnPtr = IColumn::Ptr;
using MutableColumnPtr = IColumn::MutablePtr;

using Columns = std::vector<ColumnPtr>;
using MutableColumns = std::vector<MutableColumnPtr>;

namespace cow {

template <typename Tp> Tp::Ptr static_pointer_cast(const ColumnPtr &ptr) {
    return Tp::static_pointer_cast(ptr);
}

template <typename Tp> Tp::MutablePtr static_pointer_cast(const MutableColumnPtr &ptr) {
    return Tp::static_pointer_cast(ptr);
}
} // namespace cow


template <typename Base, typename Derived, typename AncestorBase = Base>
class ColumnFactory : public Base {
private:
    Derived* mutable_derived() { return static_cast<Derived*>(this); }
    const Derived* derived() const { return static_cast<const Derived*>(this); }

public:
    template <typename... Args>
    ColumnFactory(Args&&... args) : Base(std::forward<Args>(args)...) {}

     using AncestorBaseType = std::enable_if_t<std::is_base_of_v<AncestorBase, Base>, AncestorBase>;
};

// class ConcreteColumn final : public COWHelper<IColumn, ConcreteColumn> {
//   private:
//     friend class COWHelper<IColumn, ConcreteColumn>;

//     int data;
//     explicit ConcreteColumn(int data_) : data(data_) {}
//     ConcreteColumn(const ConcreteColumn &) = default;

//   public:
//     int get() const override { return data; }
//     void set(int value) override { data = value; }
// };


// use ColumnFactory to create ConcreteColumn
class ConcreteColumn final : public COWHelper<ColumnFactory<IColumn, ConcreteColumn>, ConcreteColumn> {

  private:
    friend class COWHelper<ColumnFactory<IColumn, ConcreteColumn>, ConcreteColumn>;

    int data;

    explicit ConcreteColumn(int data_) : data(data_) {
        std::cerr << "ConcreteColumn constructor:" << data << std::endl;
    }

    ConcreteColumn(const ConcreteColumn & col) {
        std::cerr << "ConcreteColumn copy constructor" << std::endl;
        this->data = col.data;
    }

    //ConcreteColumn(const ConcreteColumn & col) = delete;
    ConcreteColumn& operator=(const ConcreteColumn&) = delete;
    ConcreteColumn(ConcreteColumn && col) = delete;
    ConcreteColumn& operator=(ConcreteColumn&&) = delete;

  public:
    int get() const override { return data; }
    void set(int value) override { data = value; }

    // not override
    void set_value(int val) { data = val; }
    int get_value() { return data; }
};
using ConcreteColumnPtr = ConcreteColumn::Ptr;
using ConcreteColumnMutablePtr = ConcreteColumn::MutablePtr;
using ConcreteColumnWrappedPtr = ConcreteColumn::DerivedWrappedPtr;

class ConcreteColumn2 final : public COWHelper<ColumnFactory<IColumn, ConcreteColumn2>, ConcreteColumn2> {

  private:
    friend class COWHelper<ColumnFactory<IColumn, ConcreteColumn2>, ConcreteColumn2>;
    using ConcreteColumnWrappedPtr = ConcreteColumn::WrappedPtr;

    ConcreteColumn2(MutableColumnPtr&& ptr) {
        std::cerr << "ConcreteColumn2 constructor" << std::endl;
        _inner = ConcreteColumn::static_pointer_cast(std::move(ptr));
    }

    // ConcreteColumn2(ColumnPtr&& ptr) {
    //     std::cerr << "ConcreteColumn2 constructor" << std::endl;
    //     _inner = ConcreteColumn::static_pointer_cast(std::move(ptr));
    // }

    // ConcreteColumn2(const ColumnPtr& ptr) {
    //     std::cerr << "ConcreteColumn2 copy constructor" << std::endl;
    //     _inner = ConcreteColumn::static_pointer_cast(ptr);
    // }

    // explicit ConcreteColumn2(const ConcreteColumnPtr &ptr) {
    //     std::cerr << "ConcreteColumn2 copy constructor" << std::endl;
    //     _inner = ptr;
    // }

    void _mock() {
        ColumnPtr x = ConcreteColumn::create(1);
        ColumnPtr y = this->create(x->assume_mutable());
    }

  public:
    int get() const override { return _inner->get(); }
    void set(int value) override { _inner->set(value); }

    // // not override
    // void set_value(int val) { _inner->set_value(val); }
    // int get_value() { return _inner->get_value(); }

  private:
    ConcreteColumnWrappedPtr _inner;
};


template <typename ColPtr>
void TRACE_COW(const std::string &msg, const ColumnPtr &x, const ColPtr &y) {
    TRACE_COW(msg, x, y, nullptr);
}

template <typename ColPtr>
void TRACE_COW(const std::string &msg, const ColumnPtr &x, const ColPtr &y, const MutableColumnPtr &mut) {
    auto get_func = [](const auto &ptr) -> int { return ptr ? ptr->get() : -1; };
    auto use_count_func = [](const auto &ptr) -> int { return ptr ? ptr->use_count() : -1; };
    auto address_func = [](const auto &ptr) -> const void * { return ptr ? ptr.get() : nullptr; };

    std::cerr << "[" << msg << "]" << "\n";
    std::cerr << "values:    " << get_func(x) << ", " << get_func(y) << ", " << get_func(mut) << "\n";
    std::cerr << "refcounts: " << use_count_func(x) << ", " << use_count_func(y) << ", " << use_count_func(mut)
              << "\n";
    std::cerr << "addresses: " << address_func(x) << ", " << address_func(y) << ", " << address_func(mut) << "\n";
}

MutableColumnPtr move_func1(MutableColumnPtr&& col) {
    return std::move(col);
}

Columns move_func2(Columns&& cols) {
    return std::move(cols);
}
MutableColumns move_func2(MutableColumns&& cols) {
    return std::move(cols);
}

TEST_F(ColumnTest, TestAssumeMutable) {
    MutableColumnPtr y;
    {
        auto x = ConcreteColumn::create(1);
        std::cout << "before assume mutable x:" << x->get() << std::endl;

        y = x->assume_mutable();
        std::cout << "after assume mutable x:" << x->get() << std::endl;
    }
    std::cout << "y:" << y->get() << std::endl;
}

TEST_F(ColumnTest, TestColumnMoveFunc) {
    MutableColumnPtr x = ConcreteColumn::create(1);
    std::cout << "x:" << x->get() << std::endl;

    MutableColumnPtr y = move_func1(std::move(x));
    std::cout << "y:" << y->get() << std::endl;

    // UD
    // std::cout << "x:" << x->get() << std::endl;
}

TEST_F(ColumnTest, TestColumnMove1) {
    MutableColumns v1;
    auto x = ConcreteColumn::create(1);
    v1.emplace_back(std::move(x));
    std::cout << "v1's size(before):" << v1.size() << std::endl;

    auto v2 = std::move(v1);
    std::cout << "v1's size(after):" << v1.size() << std::endl;
    DCHECK(0 == v1.size());
}

TEST_F(ColumnTest, TestColumnMove2) {
    MutableColumns v1;
    for (int i = 0; i < 10; i++) {
        auto x = ConcreteColumn::create(1);
        v1.emplace_back(std::move(x));
    }
    std::cout << "v1's size(before):" << v1.size() << std::endl;

    MutableColumns v2;
    for (auto& x : v1) {
        v2.emplace_back(std::move(x));
    }
    std::cout << "v1's size(after):" << v1.size() << std::endl;
    std::cout << "v2's size(after):" << v2.size() << std::endl;
    DCHECK(10 == v1.size());
    DCHECK(10 == v2.size());
}

TEST_F(ColumnTest, TestColumnMove3) {
    MutableColumns v1;
    for (int i = 0; i < 10; i++) {
        auto x = ConcreteColumn::create(1);
        v1.emplace_back(std::move(x));
    }
    std::cout << "v1's size(before):" << v1.size() << std::endl;

    MutableColumns v2 = move_func2(std::move(v1));
    std::cout << "v1's size(after):" << v1.size() << std::endl;
    std::cout << "v2's size(after):" << v2.size() << std::endl;
    DCHECK(0 == v1.size());
    DCHECK(10 == v2.size());
    for (auto& x : v2) {
        std::cout << "x:" << x->get() << std::endl;
    }
    for (auto &x : v1) {
        std::cout << "x:" << x->get() << std::endl;
    }
}

TEST_F(ColumnTest, TestColumnConvert) {
    ColumnPtr x = ConcreteColumn::create(1);
    // how to convert ColumnPtr to ConcreateColumnPtr
    // ConcreteColumnPtr x1 = std::static_pointer_cast<ConcreteColumn>(x);
    // ConcreteColumnPtr x1 = x->get_ptr();

    {
        std::cerr << "x: " << x->get() << std::endl;
        ConcreteColumnPtr x1 = ConcreteColumn::create(x);
        TRACE_COW("x, x1", x, x1);
    }

    {

        std::cerr << "x: " << x->get() << std::endl;
        ConcreteColumnPtr x1 = ConcreteColumn::static_pointer_cast(x);
        TRACE_COW("x, x1", x, x1);
        MutableColumnPtr mutable_col = x->assume_mutable();
        mutable_col->set(2);
        TRACE_COW("x, x1", x, x1);
    }
    std::cout << "final" << std::endl;
    TRACE_COW("x, x", x, x);
}


TEST_F(ColumnTest, TestConcreteColumn2) {
    {
        ColumnPtr x = ConcreteColumn::create(1);
        ColumnPtr y = ConcreteColumn2::create(x->assume_mutable());
    }
    {
        ColumnPtr y = ConcreteColumn2::create(ConcreteColumn::create(1));
    }
    {
        auto x = ConcreteColumn::create(1);
        ColumnPtr y = ConcreteColumn2::create(x->assume_mutable());
    }
    {
        auto x = ConcreteColumn::create(1);
        ColumnPtr y = ConcreteColumn2::create(std::move(x));
    }
    {
        MutableColumnPtr x = ConcreteColumn::create(1);
        ColumnPtr y = ConcreteColumn2::create(std::move(x));
    }
    {
        auto x = ConcreteColumn::create(1);
        ColumnPtr y = ConcreteColumn2::create(std::move(x));
    }
}

TEST_F(ColumnTest, TestCast) {
    ColumnPtr x = ConcreteColumn::create(1);
    ConcreteColumnPtr x1 = cow::static_pointer_cast<ConcreteColumn>(x);
    TRACE_COW("x, x1", x, x1);
}

TEST_F(ColumnTest, TestClone) {
    ColumnPtr x = ConcreteColumn::create(1);

    auto cloned = x->clone();
    // cloned is a deep copy of x, which its type is IColum, is not ConcreteColumn
    cloned->set(2);
    (static_cast<ConcreteColumn*>(cloned.get()))->set_value(3);
    ASSERT_TRUE(x->get() == 1 && cloned->get() == 3);
}

TEST_F(ColumnTest, TestCloneShared) {
    ColumnPtr x = ConcreteColumn::create(1);
    // cannot set value of cloned, because it is shared
    auto cloned = x->clone_shared();
    //cloned->set(2); !!! compile error
    ASSERT_TRUE(x->get() == 2 && cloned->get() == 1);
}


TEST_F(ColumnTest, TestCOW1) {
    ColumnPtr x = ConcreteColumn::create(1);

    // y1 is shadow copy of x, y1 and x are shared and have the same value
    auto y1 = IColumn::cow(x);
    TRACE_COW("x, y1", x, y1);
    y1->set(2);
    ASSERT_TRUE(x->get() == 2 && y1->get() == 2);
    ASSERT_TRUE(x->use_count() == 2 && y1->use_count() == 2);
    ASSERT_TRUE(x.get() == y1.get());

    // y2 is cloned from x, y2 and x are not shared and have the same value
    auto y2 = IColumn::cow(x);
    y2->set(3);
    TRACE_COW("x, y1, y2", x, y1, y2);
    ASSERT_TRUE(x->get() == 2 && y2->get() == 3);
    ASSERT_TRUE(x->use_count() == 2 && y2->use_count() == 1);
    ASSERT_TRUE(x.get() != y2.get());
}

TEST_F(ColumnTest, TestCOW2) {
    using IColumnPtr = const IColumn *;
    IColumnPtr x_ptr;
    IColumnPtr y_ptr;
    ColumnPtr x = ConcreteColumn::create(1);
    ColumnPtr y = x;

    x_ptr = x.get();
    y_ptr = y.get();
    TRACE_COW("1. <x, y> shared column", x, y);
    ASSERT_TRUE(x->get() == 1 && y->get() == 1);
    ASSERT_TRUE(x->use_count() == 2 && y->use_count() == 2);
    ASSERT_TRUE(x.get() == y.get());
    ASSERT_TRUE(x_ptr == y_ptr);
    {
        // move y to mut, y is moved
        // because x and y are shared which its use_cout is greater than 1, y is cloned(deep copy)
        MutableColumnPtr mut = IColumn::mutate(std::move(y));
        ASSERT_TRUE(y.get() == nullptr);
        TRACE_COW("2. <x, y, mut> ", x, y, mut);

        mut->set(2);
        TRACE_COW("2. <x, y, mut> ", x, y, mut);
        ASSERT_TRUE(x->get() == 1 && mut->get() == 2);
        ASSERT_TRUE(x->use_count() == 1 && mut->use_count() == 1);
        ASSERT_TRUE(x.get() != mut.get());

        y = std::move(mut);
        y_ptr = y.get();
        ASSERT_TRUE(x_ptr != y_ptr);
        TRACE_COW("2. <x, y, mut> ", x, y, mut);
    }
    TRACE_COW("3. <x, y, mut>", x, y);
    ASSERT_TRUE(x->get() == 1 && y->get() == 2);
    ASSERT_TRUE(x->use_count() == 1 && y->use_count() == 1);
    ASSERT_TRUE(x.get() != y.get());
    ASSERT_TRUE(x_ptr != y_ptr);
    ASSERT_TRUE(y_ptr == y.get());

    x = ConcreteColumn::create(0);
    TRACE_COW("4. <x, y, mut>", x, y);
    ASSERT_TRUE(x->get() == 0 && y->get() == 2);
    ASSERT_TRUE(x->use_count() == 1 && y->use_count() == 1);
    ASSERT_TRUE(x.get() != y.get());
    ASSERT_TRUE(y_ptr == y.get());

    // shadow copy
    {
        // move y to mut, y is moved, because x and y are not shared, y is shadow copy of mut
        // and its address is the same as mut
        MutableColumnPtr mut = IColumn::mutate(std::move(y));
        ASSERT_TRUE(y.get() == nullptr);
        TRACE_COW("5. <x, y, mut>", x, y, mut);

        mut->set(3);
        TRACE_COW("5. <x, y, mut>", x, y, mut);
        ASSERT_TRUE(x->get() == 0 && mut->get() == 3);
        ASSERT_TRUE(x->use_count() == 1 && mut->use_count() == 1);
        ASSERT_TRUE(x.get() != mut.get());

        // y is shadow copy of mut, its address is the same as mut
        y = std::move(mut);
        ASSERT_TRUE(y_ptr == y.get());
        TRACE_COW("5. <x, y, mut>", x, y, mut);
    }
    TRACE_COW("6. <x, y, mut>", x, y);
    ASSERT_TRUE(x->get() == 0 && y->get() == 3);
    ASSERT_TRUE(x->use_count() == 1 && y->use_count() == 1);
    ASSERT_TRUE(x.get() != y.get());
    ASSERT_TRUE(y_ptr == y.get());

    // deep copy
    {
        // y is not moved, it is a mutate of y
        MutableColumnPtr mut = IColumn::mutate(y);
        mut->set(3);
        TRACE_COW("7. <x, y, mut>", x, y, mut);
        ASSERT_TRUE(x->get() == 0 && mut->get() == 3);
        ASSERT_TRUE(x->use_count() == 1 && mut->use_count() == 1);
        ASSERT_TRUE(y.get() != mut.get());

        y = std::move(mut);
        ASSERT_TRUE(y_ptr != y.get());
        TRACE_COW("7. <x, y, mut>", x, y, mut);
    }
    TRACE_COW("8. <x, y, mut>", x, y);
    ASSERT_TRUE(x->get() == 0 && y->get() == 3);
    ASSERT_TRUE(x->use_count() == 1 && y->use_count() == 1);
    ASSERT_TRUE(x.get() != y.get());
    ASSERT_TRUE(y_ptr != y.get());
}

} // namespace test
