#include <async_lab/measure.hpp>
#include <iostream>
#include <liburing/io_service.hpp>
#include <vector>

namespace {
uio::Task<int> Child(uio::IoService& service) {
    async_lab::Require(co_await service.Nop() == 0, "NOP failed");
    co_return 42;
}
uio::Task<> Parent(uio::IoService& service) {
    async_lab::Require(co_await Child(service) == 42, "nested result mismatch");
}
uio::Task<> Failure(uio::IoService& service) {
    co_await service.Nop();
    throw std::runtime_error("expected task error");
}
} // namespace
int main() {
    try {
        uio::IoService service(2);
        std::vector<uio::Task<>> tasks;
        for (int i = 0; i < 100; ++i) tasks.push_back(Parent(service));
        service.RunAll(tasks);
        async_lab::Require(service.completions == 100, "duplicate/missing completion");
        auto failure = Failure(service);
        bool caught = false;
        try {
            service.Run(failure);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        async_lab::Require(caught, "exception was lost");
        std::cout << "PASS nested tasks, 100 completions on depth=2, bounded startup, exception "
                     "propagation\n";
    } catch (const std::system_error& e) {
        std::cerr << e.what() << '\n';
        return (e.code().value() == ENOSYS || e.code().value() == EPERM) ? 77 : 1;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
