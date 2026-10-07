// Agent-authored deterministic ground-truth checks; no LLM-generated code is executed.
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 2) {
        return 2;
    }
    const std::string mode(argv[1]);
    if (mode == "bounds") {
        const std::vector<int> values{1, 2, 3};
        int result = 0;
        for (std::size_t i = 0; i <= values.size(); ++i) {
            result += values[i];
        }
        return result;
    }
    if (mode == "lifetime") {
        int* p = new int(42);
        delete p;
        return *p;
    }
    return 2;
}
