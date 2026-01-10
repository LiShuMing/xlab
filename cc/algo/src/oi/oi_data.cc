#include "../include/fwd.h"
class IOLinkTable {
public:
    void insert(int val, ListNode* p) {
        ListNode* node = new ListNode(val);
        node->next = p->next;
        p->next = node;
    }
};

class IOHashTable {
public:
    static const int HT_SIZE = 1000;
    static const int HT_M = 9997;

    struct HashTable {
        struct Node {
            int next;
            int value;
            int key;
        } data[HT_SIZE];

        int head[HT_M];
        int size;

        int f(int key) { return (key % HT_M + HT_M) % HT_M; }

        int get(int key) {
            for (int p = head[f(key)]; p; p = data[p].next) {
                if (data[p].key == key) {
                    return data[p].value;
                }
            }
            return -1;
        }

        int modify(int key, int value) {
            for (int p = head[f(key)]; p; p = data[p].next) {
                if (data[p].key == key) {
                    data[p].value = value;
                    return value;
                }
            }
            return -1;
        }

        int add(int key, int value) {
            if (get(key) != -1) {
                return -1;
            }
            data[++size] = Node {head[f(key)], value, key}; // 使用前向星结构
            head[f(key)] = size;
            return value;
        }
    };

    struct hash_map { // 哈希表模板
        struct data {
            long long u;
            int v;
            int next;
        }; // 前向星结构

        data e[HT_SIZE << 1]; // HT_SIZE 是 const int 表示大小
        int h[HT_SIZE], cnt;

        hash_map() {
            cnt = 0;
            memset(h, 0, sizeof(h));
        }

        int hash(long long u) { return (u % HT_SIZE + HT_SIZE) % HT_SIZE; }

        // 这里使用 (u % SZ + SZ) % SZ 而非 u % SZ 的原因是
        // C++ 中的 % 运算无法将负数转为正数
        int& operator[](long long u) {
            int hu = hash(u); // 获取头指针
            for (int i = h[hu]; i; i = e[i].next) {
                if (e[i].u == u) {
                    return e[i].v;
                }
            }
            return e[++cnt] = data {u, -1, h[hu]}, h[hu] = cnt, e[cnt].value;
        }
    };

    class Hash {
    private:
        int keys[HT_SIZE];
        int values[HT_SIZE];

    public:
        Hash() { memset(values, 0, sizeof(values)); }

        int& operator[](int n) {
            // 返回一个指向对应 Hash[Key] 的引用
            // 修改成不为 0 的值 0 时候视为空
            int idx = (n % HT_SIZE + HT_SIZE) % HT_SIZE, cnt = 1;
            while (keys[idx] != n && values[idx] != 0) {
                idx = (idx + cnt * cnt) % HT_SIZE;
                cnt += 1;
            }
            keys[idx] = n;
            return values[idx];
        }
    };
};