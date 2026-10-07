// An independently written check against the actual, unmodified xlab header.
#include "task_thread.h"
#include <iostream>
#include <string>

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    const std::string mode(argv[1]);
    if (mode != "control" && mode != "reentrant") {
        return 2;
    }
    xlab::TaskThread thread("review-check", xlab::TaskThread::RELEASE_MODE_DO_ALL_DONE);
    thread.start();
    thread.add([&] {
        std::cerr << "callback_entered\n";
        if (mode == "reentrant") {
            thread.add([] {});
        }
        std::cerr << "callback_returned\n";
    }, 60000);
    // DO_ALL_DONE executes even this future task during shutdown.
    thread.stop_and_join();
    std::cerr << "shutdown_returned\n";
    return 0;
}
