#include <stdexcept>

#include "../include/fwd.h"

class SnapshotArray {
public:
    SnapshotArray(int length) {
        this->snap_id_ = 0;
        this->data_.resize(length);
    }

    void set(int index, int val) { 
        data_[index].emplace_back(snap_id_, val);
    }

    int snap() {
        return snap_id_++;
    }

    int get(int index, int snap_id) { 
        auto it = upper_bound(data_[index].begin(), data_[index].end(), pair<int, int>{snap_id + 1, -1});
        return it == data_[index].begin() ? 0 : prev(it)->second;
    }

private:
    vector<vector<pair<int, int>>> data_;
    int snap_id_;
};

/**
     * Your SnapshotArray object will be instantiated and called as such:
     * SnapshotArray* obj = new SnapshotArray(length);
     * obj->set(index,val);
     * int param_2 = obj->snap();
     * int param_3 = obj->get(index,snap_id);
     */
int main() {
    SnapshotArray snapshotArray(3);
    snapshotArray.set(0, 5);
    snapshotArray.snap();
    snapshotArray.set(0, 6);
    cout << snapshotArray.get(0, 0) << endl;
    return 0;
}