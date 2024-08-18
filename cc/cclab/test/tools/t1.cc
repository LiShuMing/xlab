#include <concepts>
#include <cstddef>
#include <functional>
#include <iostream>
#include <type_traits>
template <typename T, template <typename...> class Z>
struct is_specialization_of : std::false_type {};
template <typename... Args, template <typename...> class Z>
struct is_specialization_of<Z<Args...>, Z> : std::true_type {};

template <typename T, template <typename...> class Z>
concept specialization_of = is_specialization_of<T, Z>::value;
template <typename T> struct chain {
    T wrapped_value;
};
template <typename L, typename R, typename Op> class binary_expr {
    L lhs;
    R rhs;

  public:
    constexpr binary_expr(L lhs, R rhs) : lhs(lhs), rhs(rhs) {}
    constexpr auto &get_left_most() const {
        if constexpr (specialization_of<L, binary_expr>) {
            return lhs.get_left_most();
        } else {
            return lhs;
        }
    }
    constexpr auto &get_right_most() const {
        if constexpr (specialization_of<R, binary_expr>) {
            return rhs.get_right_most();
        } else {
            return rhs;
        }
    }
    template <typename T> constexpr auto &maybe_unwrap(const chain<T> &value) const {
        return value.wrapped_value;
    }
    template <typename T> constexpr auto &maybe_unwrap(const T &value) const { return value; }
    constexpr operator bool() const {
        auto &lhs = maybe_unwrap(this->lhs);
        auto &rhs = maybe_unwrap(this->rhs);
        if constexpr (specialization_of<L, binary_expr> && specialization_of<R, binary_expr>) {
            return lhs && Op{}(lhs.get_right_most(), rhs.get_left_most()) && rhs;
        } else if constexpr (!specialization_of<L, binary_expr> &&
                             specialization_of<R, binary_expr>) {
            return Op{}(lhs, rhs.get_left_most()) && rhs;
        } else if constexpr (specialization_of<L, binary_expr> &&
                             !specialization_of<R, binary_expr>) {
            return lhs && Op{}(lhs.get_right_most(), rhs);
        } else {
            return Op{}(lhs, rhs);
        }
    }
};

template <typename L, typename R> using equal_to1 = binary_expr<L, R, std::equal_to<void>>;
template <typename L, typename R> using not_equal_to1 = binary_expr<L, R, std::not_equal_to<void>>;
template <typename L, typename R> using greater = binary_expr<L, R, std::greater<void>>;
template <typename L, typename R> using less = binary_expr<L, R, std::less<void>>;
template <typename L, typename R> using greater_equal = binary_expr<L, R, std::greater_equal<void>>;
template <typename L, typename R> using less_equal = binary_expr<L, R, std::less_equal<void>>;

template <typename T>
concept chainable = specialization_of<T, binary_expr> || specialization_of<T, chain>;
template <typename L, typename R>
concept can_chain = chainable<L> || chainable<R>;

template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator==(L lhs, R rhs) {
    return equal_to1(lhs, rhs);
}
template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator!=(L lhs, R rhs) {
    return not_equal_to1(lhs, rhs);
}
template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator>(L lhs, R rhs) {
    return greater(lhs, rhs);
}
template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator<(L lhs, R rhs) {
    return less(lhs, rhs);
}
template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator>=(L lhs, R rhs) {
    return greater_equal(lhs, rhs);
}
template <typename L, typename R>
    requires(can_chain<L, R>)
constexpr auto operator<=(L lhs, R rhs) {
    return less_equal(lhs, rhs);
}

constexpr auto operator""_chain(unsigned long long value) { return chain(static_cast<int>(value)); }

int main() {
    int x = 150;
    std::cout << std::boolalpha << (100_chain <= x <= 200); // prints true
}
