// 运行 make -C cc/algo/src/oi demo：从操作表开始，逐步观察时间树 DFS 和回滚。
#include "../include/fwd.h"
#include "offline_dynamic_connectivity.h"

int main() {
    try {
        using oi::Kind;
        // 0=A、1=B、2=C。每一行是一条操作，数组下标就是操作的时间。
        // 特意先加 0-1，再加 1-2，随后删除更早加入的 0-1：
        // 普通并查集不能直接删这条旧边，但时间树能把它变为局部分支里的回滚。
        const std::vector<oi::Operation> operations = {
                {Kind::Add, 0, 1},     // t=0：A-B
                {Kind::Add, 1, 2},     // t=1：A-B-C
                {Kind::Query, 0, 2},   // t=2：YES
                {Kind::Remove, 0, 1},  // t=3：A    B-C
                {Kind::Query, 0, 2},   // t=4：NO
                {Kind::Add, 0, 2},     // t=5：A-C-B
                {Kind::Query, 0, 1},   // t=6：YES
                {Kind::Remove, 0, 2},  // t=7：A    B-C
                {Kind::Query, 0, 1},   // t=8：NO；1-2 到输入结束仍然活跃
        };
        std::cout << "=== 0. 操作时间表（0=A, 1=B, 2=C）===\n";
        for (std::size_t t = 0; t < operations.size(); ++t) {
            const auto& op = operations[t];
            const char* name = op.kind == Kind::Add ? "ADD   "
                               : op.kind == Kind::Remove ? "REMOVE" : "QUERY ";
            std::cout << "t=" << t << ' ' << name << ' ' << op.u << '-' << op.v << '\n';
        }

        const oi::OfflineDynamicConnectivity solver(3, operations);
        solver.explainSchedule(std::cout);
        std::cout << "=== 2. DFS（缩进表示深度；先保存、再加边、最后恢复）===\n";
        const auto answers = solver.solve(&std::cout);
        std::cout << "=== 3. 叶子询问答案（手算应为 YES / NO / YES / NO）===\n";
        const std::vector<bool> expected = {true, false, true, false};
        if (answers.size() != expected.size()) throw std::runtime_error("wrong answer count");
        for (std::size_t i = 0; i < answers.size(); ++i) {
            const auto& answer = answers[i];
            std::cout << "t=" << answer.time << ' ' << answer.u << '~' << answer.v << " => "
                      << (answer.connected ? "YES" : "NO") << '\n';
            // 不依赖 assert；-DNDEBUG 的发布构建也会验证演示结果。
            if (answer.connected != expected[i]) throw std::runtime_error("demo answer mismatch");
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "demo failed: " << error.what() << '\n';
        return 1;
    }
}
