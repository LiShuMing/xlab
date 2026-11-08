#include <async_lab/measure.hpp>
#include <iostream>
#include <liburing/io_service.hpp>
#include <liburing/utils.hpp>
#include <vector>

namespace {
uio::Task<> Timer(uio::IoService& service) {
    auto duration = uio::Duration(std::chrono::milliseconds(10));
    const auto start = async_lab::NowNs();
    async_lab::Require(co_await service.Timeout(&duration) == -ETIME, "timeout result");
    async_lab::Require(async_lab::NowNs() - start >= 10000000, "timer completed early");
}
uio::Task<> WaitCancelled(uio::IoService& service, uio::IoAwaitable** pending) {
    auto duration = uio::Duration(std::chrono::seconds(5));
    auto operation = service.Timeout(&duration);
    *pending = &operation;
    async_lab::Require(co_await operation == -ECANCELED, "target was not cancelled");
}
uio::Task<> Cancel(uio::IoService& service, uio::IoAwaitable** pending) {
    async_lab::Require(*pending != nullptr, "no pending operation");
    async_lab::Require(co_await service.Cancel(**pending) == 0, "cancel failed");
}
} // namespace
int main() {
    try {
        uio::IoService service;
        auto timer = Timer(service);
        service.Run(timer);
        uio::IoAwaitable* pending = nullptr;
        std::vector<uio::Task<>> tasks;
        tasks.push_back(WaitCancelled(service, &pending));
        tasks.push_back(Cancel(service, &pending));
        service.RunAll(tasks);
        async_lab::Require(service.completions == 3, "cancel completion accounting");
        std::cout << "PASS 10ms timer, cancellation acknowledgement and target completion\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
