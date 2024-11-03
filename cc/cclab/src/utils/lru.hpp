
#pragma once

#include <list>
#include <map>

namespace xlab {

/**
 * 
 *     ```
    xlab::lru<std::string, int> c(3);
    c.put("xlab", 1);
    c.put("yoko", 2);
    c.put("tom", 3);
    c.put("jerry", 4); // 超过容器大小，淘汰最老的`xlab`
    bool exist;
    int v;
    exist = c.get("xlab", &v);
    //assert(!exist);
    exist = c.get("yoko", &v);
    //assert(exist && v == 2);
    c.put("garfield", 5); // 超过容器大小，注意，由于`yoko`刚才读取时会更新热度，所以淘汰的是`tom`
    exist = c.get("yoko", &v);
    //assert(exist && v == 2);
    exist = c.get("tom", &v);
    //assert(!exist);
    ```
 */

template <typename KeyT, typename ValueT> class lru {
  public:
    typedef std::pair<KeyT, ValueT> KVPair;
    typedef std::list<KVPair> List;

  public:
    explicit lru(std::size_t cap);
    ~lru();

  public:
    // true if key not exist before, false otherwise
    bool put(KeyT k, ValueT v);

    // true if key exist, false otherwise
    bool get(KeyT k, ValueT *v);

    std::list<KVPair> get_list();

    std::size_t size() const;
    std::size_t capacity() const;

  private:
    lru(const lru &);
    lru &operator=(const lru &);

  private:
    typedef std::map<KeyT, typename List::iterator> Map;

  private:
    const std::size_t capacity_;
    List list_;
    Map map_;

}; // class lru

} // namespace xlab
namespace xlab {

template <typename KeyT, typename ValueT>
lru<KeyT, ValueT>::lru(std::size_t cap) : capacity_(cap) {}

template <typename KeyT, typename ValueT> lru<KeyT, ValueT>::~lru() {
    list_.clear();
    map_.clear();
}

template <typename KeyT, typename ValueT> bool lru<KeyT, ValueT>::put(KeyT k, ValueT v) {
    bool not_exist = true;
    typename Map::iterator iter = map_.find(k);
    if (iter != map_.end()) {
        list_.erase(iter->second);
        map_.erase(iter);
        not_exist = false;
    }

    list_.push_front(std::make_pair(k, v));
    map_[k] = list_.begin();

    if (list_.size() > capacity_) {
        KeyT old = list_.back().first;
        list_.pop_back();
        map_.erase(old);
    }
    return not_exist;
}

template <typename KeyT, typename ValueT> bool lru<KeyT, ValueT>::get(KeyT k, ValueT *v) {
    typename Map::iterator iter = map_.find(k);
    if (iter == map_.end()) {
        return false;
    }
    KVPair kvp = *(iter->second);
    list_.erase(iter->second);
    list_.push_front(kvp);
    map_[k] = list_.begin();
    *v = kvp.second;
    return true;
}

template <typename KeyT, typename ValueT> std::size_t lru<KeyT, ValueT>::size() const {
    return list_.size();
}

template <typename KeyT, typename ValueT> std::size_t lru<KeyT, ValueT>::capacity() const {
    return capacity_;
}

template <typename KeyT, typename ValueT>
typename lru<KeyT, ValueT>::List lru<KeyT, ValueT>::get_list() {
    return list_;
}

} // namespace xlab

#endif // _xlab_BASE_LRU_HPP_
