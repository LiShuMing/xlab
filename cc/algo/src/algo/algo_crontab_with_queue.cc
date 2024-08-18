#include "../include/fwd.h"
#include <iostream>
#include <vector>
#include <queue>
#include <chrono>
#include <thread>
#include <functional>
#include <string>
#include <iomanip>

using namespace std;
using namespace std::chrono;

// 1. 任务类设计
struct CronTask {
    string id;
    seconds interval; // 模拟 Cron 间隔
    system_clock::time_point next_run_time;
    function<void()> action;

    // 构造函数
    CronTask(string name, int sec, function<void()> func) 
        : id(name), interval(sec), action(func) {
        next_run_time = system_clock::now() + interval;
    }

    // 2. 关键：自定义比较器（用于优先队列构建小顶堆）
    // 执行时间越早，优先级越高
    bool operator>(const CronTask& other) const {
        return next_run_time > other.next_run_time;
    }
};

class CronScheduler {
private:
    // 使用 greater 构建小顶堆
    priority_queue<CronTask, vector<CronTask>, greater<CronTask>> pq;

public:
    void addTask(CronTask task) {
        pq.push(task);
    }

    void run() {
        cout << "调度器启动..." << endl;

        while (!pq.empty()) {
            // 获取堆顶最紧迫的任务
            CronTask current = pq.top();
            auto now = system_clock::now();

            if (now < current.next_run_time) {
                // 情况 A：时间未到，让线程休眠差值
                auto wait_time = current.next_run_time - now;
                this_thread::sleep_for(wait_time);
                continue; 
            }

            // 情况 B：时间已到，执行并更新
            pq.pop();
            
            // 输出执行时间点
            auto t_c = system_clock::to_time_t(system_clock::now());
            cout << "[" << put_time(localtime(&t_c), "%H:%M:%S") << "] " 
                 << "执行: " << current.id << endl;
            
            current.action();

            // 计算下一次运行时间并重新入堆
            current.next_run_time += current.interval;
            pq.push(current);
        }
    }
};

int main() {
    CronScheduler scheduler;

    scheduler.addTask(CronTask("Task_A", 2, []() { cout << "  -> A Done" << endl; }));
    scheduler.addTask(CronTask("Task_B", 5, []() { cout << "  -> B Done" << endl; }));

    scheduler.run();
    return 0;
}
