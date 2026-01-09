#include "../include/fwd.h"
class LinkTable {
public:
    void insert(int val, ListNode* p) {
        ListNode* node = new ListNode(val);
        node->next = p->next;
        p->next = node;
    }

};