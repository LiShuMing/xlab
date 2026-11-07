#include "../include/fwd.h"

#include <sys/stat.h>
#include <sys/types.h>

#include <cstdint>
#include <fstream>
#include <random>

/**
 * 外存精确去重：64 位 ID 无法全部装进内存，输出不重复 ID（不要求顺序）。
 *
 * 三条不变量决定了整个结构：
 *   1. 同一 ID 必须进入同一分区：分区键只由 ID 决定，用固定混合函数，不用 std::hash
 *      （后者可能带盐，跨进程不稳定）。否则“分区内去重”不等于“全局去重”。
 *   2. 同时打开的句柄数与数据量无关：固定扇出 kFanout，靠多层哈希位逐层细分，
 *      而不是“算出一个刚好装得下的分区数”。
 *   3. 分区字节数大不代表唯一值多：单值重复的分区哈希切不动，切到层数上限后
 *      退化为外部排序 + 归并去重，不能无限递归。
 *
 * 内存预算按哈希表单条记录约 32 字节估算；生产实现应把系数和分配器开销算准，
 * 否则会在最后一层放大成 OOM。
 */
namespace {

constexpr size_t kBatch = 1u << 16;  // 批量读写的记录数
constexpr size_t kEntryCost = 32;    // 哈希表每条记录的内存估算（字节）
constexpr int kFanoutBits = 4;       // 每层 16 个分区
constexpr int kFanout = 1 << kFanoutBits;
constexpr int kMaxLevel = 3;         // 最多向下切 3 层，共用到 16 位哈希

// splitmix64 收尾混淆：让高位充分混合，避免低位相似的 ID 挤进同一个分区
uint64_t mix64(uint64_t x) {
    x += 0x9e3779b97f4a7c15ULL;
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

size_t file_entries(const string& path) {
    struct stat st;
    if (stat(path.c_str(), &st) != 0) return 0;
    return static_cast<size_t>(st.st_size) / sizeof(uint64_t);
}

// 最多读 max 条；返回实际条数
size_t read_upto(ifstream& in, vector<uint64_t>& buf, size_t max) {
    buf.resize(max);
    in.read(reinterpret_cast<char*>(buf.data()),
            static_cast<streamsize>(max * sizeof(uint64_t)));
    size_t got = static_cast<size_t>(in.gcount()) / sizeof(uint64_t);
    buf.resize(got);
    return got;
}

class ExternalDedup {
public:
    ExternalDedup(const string& dir, size_t mem_bytes)
        : dir_(dir), max_entries_(max<size_t>(1, mem_bytes / kEntryCost)) {}

    // 返回去重后的记录数
    long long run(const string& in, const string& out) {
        mkdir(dir_.c_str(), 0755);
        out_.open(out, ios::binary | ios::trunc);
        if (!out_.is_open()) return -1;
        dedup(in, 0);
        out_.close();
        return distinct_;
    }

    size_t partitions() const { return partitions_; }
    int fallback_uses() const { return fallback_uses_; }
    size_t max_entries() const { return max_entries_; }

private:
    void dedup(const string& path, int level) {
        size_t entries = file_entries(path);
        if (entries <= max_entries_) {
            dedup_in_memory(path);  // 装得下：哈希表直接去重
            return;
        }
        if (level < kMaxLevel) {
            vector<string> parts = split(path, level);
            for (const auto& p : parts) dedup(p, level + 1);
            for (const auto& p : parts) remove(p.c_str());
            return;
        }
        external_sort_dedup(path);  // 哈希已切不动（倾斜/单值重复），改用排序
    }

    // 按第 level 层哈希位切成 kFanout 个文件，返回文件名
    vector<string> split(const string& path, int level) {
        const int shift = 64 - kFanoutBits * (level + 1);
        vector<string> names(kFanout);
        vector<ofstream> outs(kFanout);  // 同时只开 kFanout 个写句柄
        for (int i = 0; i < kFanout; ++i) {
            names[i] = dir_ + "/l" + to_string(level) + "_b" + to_string(i);
            outs[i].open(names[i], ios::binary | ios::trunc);
            if (!outs[i].is_open()) return {};
        }
        partitions_ += kFanout;

        ifstream in(path, ios::binary);
        vector<uint64_t> buf;
        while (read_upto(in, buf, kBatch) > 0) {
            for (uint64_t id : buf) {
                int bucket = static_cast<int>((mix64(id) >> shift) & (kFanout - 1));
                outs[bucket].write(reinterpret_cast<const char*>(&id), sizeof(id));
            }
        }
        for (auto& o : outs) o.close();
        return names;
    }

    void dedup_in_memory(const string& path) {
        unordered_set<uint64_t> seen;
        ifstream in(path, ios::binary);
        vector<uint64_t> buf;
        while (read_upto(in, buf, kBatch) > 0) {
            for (uint64_t id : buf) {
                if (seen.insert(id).second) write_one(id);
            }
        }
    }

    // 哈希倾斜时的兜底：分块排序落盘，再多路归并，相邻重复只留一个
    void external_sort_dedup(const string& path) {
        ++fallback_uses_;
        vector<string> runs;
        ifstream in(path, ios::binary);
        vector<uint64_t> chunk;
        while (read_upto(in, chunk, max_entries_) > 0) {
            sort(chunk.begin(), chunk.end());
            string run_path = dir_ + "/run_" + to_string(runs.size());
            ofstream ro(run_path, ios::binary | ios::trunc);
            ro.write(reinterpret_cast<const char*>(chunk.data()),
                     static_cast<streamsize>(chunk.size() * sizeof(uint64_t)));
            ro.close();
            runs.push_back(run_path);
        }

        struct Node {
            uint64_t value;
            size_t run;
        };
        struct Cmp {
            bool operator()(const Node& a, const Node& b) const { return a.value > b.value; }
        };
        priority_queue<Node, vector<Node>, Cmp> heap;
        vector<ifstream> ins(runs.size());
        for (size_t i = 0; i < runs.size(); ++i) {
            ins[i].open(runs[i], ios::binary);
            uint64_t v = 0;
            if (ins[i].read(reinterpret_cast<char*>(&v), sizeof(v))) heap.push({v, i});
        }

        bool has_last = false;
        uint64_t last = 0;
        while (!heap.empty()) {
            Node top = heap.top();
            heap.pop();
            if (!has_last || top.value != last) {
                write_one(top.value);
                has_last = true;
                last = top.value;
            }
            uint64_t v = 0;
            if (ins[top.run].read(reinterpret_cast<char*>(&v), sizeof(v))) {
                heap.push({v, top.run});
            }
        }
        for (auto& i : ins) i.close();
        for (const auto& r : runs) remove(r.c_str());
    }

    void write_one(uint64_t id) {
        out_.write(reinterpret_cast<const char*>(&id), sizeof(id));
        ++distinct_;
    }

    string dir_;
    size_t max_entries_;
    ofstream out_;
    long long distinct_ = 0;
    size_t partitions_ = 0;
    int fallback_uses_ = 0;
};

void write_ids(const string& path, const vector<uint64_t>& ids) {
    ofstream out(path, ios::binary | ios::trunc);
    out.write(reinterpret_cast<const char*>(ids.data()),
              static_cast<streamsize>(ids.size() * sizeof(uint64_t)));
}

vector<uint64_t> read_ids(const string& path) {
    ifstream in(path, ios::binary);
    vector<uint64_t> ids;
    uint64_t v = 0;
    while (in.read(reinterpret_cast<char*>(&v), sizeof(v))) ids.push_back(v);
    return ids;
}

}  // namespace

int main() {
    const string base = "/tmp/xlab_ext_dedup";
    mkdir(base.c_str(), 0755);
    mt19937_64 rng(20261102);

    // 用例 1：均匀重复。ID 来自 0..D-1，每个至少出现一次，其余随机补足
    {
        const uint64_t kUniverse = 200000;
        const size_t kRecords = 800000;
        vector<uint64_t> ids;
        ids.reserve(kRecords);
        for (uint64_t i = 0; i < kUniverse; ++i) ids.push_back(i);
        while (ids.size() < kRecords) ids.push_back(rng() % kUniverse);
        shuffle(ids.begin(), ids.end(), rng);

        const string in = base + "/in1.bin", out = base + "/out1.bin";
        write_ids(in, ids);
        ExternalDedup dedup(base, 128 * 1024);
        long long distinct = dedup.run(in, out);

        // 校验侧不受预算限制：直接全量装进内存对照
        vector<uint64_t> got = read_ids(out);
        unordered_set<uint64_t> uniq(got.begin(), got.end());
        bool ok = distinct == static_cast<long long>(kUniverse) &&
                  got.size() == kUniverse && uniq.size() == kUniverse;
        for (uint64_t x : uniq) ok = ok && x < kUniverse;
        cout << "[用例1 均匀重复] 记录 " << kRecords << " -> 去重 " << distinct << "（期望 "
             << kUniverse << "）分区 " << dedup.partitions() << " 个, 兜底 "
             << dedup.fallback_uses() << " 次: " << (ok ? "ok" : "FAIL") << endl;
        if (!ok) return 1;
    }

    // 用例 2：极端倾斜。99% 是同一条记录，哈希怎么切都在同一个桶里
    {
        const uint64_t kSalt = 0xDEADBEEFCAFEULL;
        const uint64_t kTail = 1000;
        vector<uint64_t> ids;
        ids.reserve(200000);
        ids.push_back(kSalt);
        for (uint64_t i = 1; i <= kTail; ++i) ids.push_back(i);
        while (ids.size() < 200000) {
            ids.push_back((ids.size() % 100) ? kSalt : (1 + rng() % kTail));
        }
        shuffle(ids.begin(), ids.end(), rng);

        const string in = base + "/in2.bin", out = base + "/out2.bin";
        write_ids(in, ids);
        ExternalDedup dedup(base, 128 * 1024);
        long long distinct = dedup.run(in, out);

        vector<uint64_t> got = read_ids(out);
        unordered_set<uint64_t> uniq(got.begin(), got.end());
        bool ok = distinct == static_cast<long long>(kTail + 1) && got.size() == kTail + 1 &&
                  uniq.size() == kTail + 1 && uniq.count(kSalt) == 1;
        cout << "[用例2 极端倾斜] 记录 200000 -> 去重 " << distinct << "（期望 "
             << kTail + 1 << "）分区 " << dedup.partitions() << " 个, 兜底 "
             << dedup.fallback_uses() << " 次: " << (ok ? "ok" : "FAIL") << endl;
        if (!ok) return 1;
    }

    // 用例 3：小输入，直接走内存路径，不产生分区文件
    {
        vector<uint64_t> ids = {7, 7, 7, 42, 9, 42};
        const string in = base + "/in3.bin", out = base + "/out3.bin";
        write_ids(in, ids);
        ExternalDedup dedup(base, 128 * 1024);
        long long distinct = dedup.run(in, out);

        vector<uint64_t> got = read_ids(out);
        sort(got.begin(), got.end());
        bool ok = distinct == 3 && got == vector<uint64_t>({7, 9, 42}) &&
                  dedup.partitions() == 0;
        cout << "[用例3 内存路径] 记录 6 -> 去重 " << distinct << "（期望 3）分区 "
             << dedup.partitions() << " 个: " << (ok ? "ok" : "FAIL") << endl;
        if (!ok) return 1;
    }

    cout << "外存去重全部用例通过" << endl;
    return 0;
}
