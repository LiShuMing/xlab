#include <cmath>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <mutex>

#define STORE_FILE "store/dumpFile"

std::mutex mtx; // mutex for critical section
std::string delimiter = ":";

// Class template to implement node
template <typename K, typename V>
class Node {
public:
    Node() {}
    Node(K k, V v, int level) : key(k), value(v), node_level(level) {
        next = new Node<K, V>*[level + 1];
        memset(next, 0, sizeof(Node<K, V>*) * (level + 1));
    }
    ~Node() { delete[] next; }

    K get_key() const { return key; }

    V get_value() const { return value; }

    void set_value(V value) { this->value = value; }

    // next[i] is the next node of current node at the same level i
    Node<K, V>** next;
    int node_level;

private:
    K key;
    V value;
};

// Class template for Skip list
template <typename K, typename V>
class SkipList {
public:
    SkipList(int max_level) {
        this->_max_level = max_level;
        this->_skip_list_level = 0;
        this->_element_count = 0;

        // NOTE: It's important to initialize the header node with key and value to null
        // create header node and initialize key and value to null
        K k;
        V v;
        this->_header = new Node<K, V>(k, v, _max_level);
    }

    ~SkipList() {
        if (_file_writer.is_open()) {
            _file_writer.close();
        }
        if (_file_reader.is_open()) {
            _file_reader.close();
        }

        if (_header->next[0] != nullptr) {
            clear(_header->next[0]);
        }
        delete (_header);
    }

    int get_random_level() {
        int k = 1;
        while (rand() % 2) {
            k++;
        }
        k = (k < _max_level) ? k : _max_level;
        return k;
    }

    Node<K, V>* create_node(const K k, const V v, int level) {
        Node<K, V>* n = new Node<K, V>(k, v, level);
        return n;
    }

    int insert_element(const K key, const V value) {
        mtx.lock();
        Node<K, V>* current = this->_header;

        // create update array and initialize it
        // update is array which put node that the node->next[i] should be operated later
        Node<K, V>* update[_max_level + 1];
        memset(update, 0, sizeof(Node<K, V>*) * (_max_level + 1));

        // start form highest level of skip list
        for (int i = _skip_list_level; i >= 0; i--) {
            while (current->next[i] != NULL && current->next[i]->get_key() < key) {
                current = current->next[i];
            }
            update[i] = current;
        }

        // reached level 0 and next pointer to right node, which is desired to insert key.
        current = current->next[0];

        // if current node have key equal to searched key, we get it
        if (current != NULL && current->get_key() == key) {
            std::cout << "key: " << key << ", exists" << std::endl;
            mtx.unlock();
            return 1;
        }

        // if current is NULL that means we have reached to end of the level
        // if current's key is not equal to key that means we have to insert node between update[0] and current node
        if (current == NULL || current->get_key() != key) {
            // Generate a random level for node
            int random_level = get_random_level();

            // If random level is greater thar skip list's current level, initialize update value with pointer to header
            if (random_level > _skip_list_level) {
                for (int i = _skip_list_level + 1; i < random_level + 1; i++) {
                    update[i] = _header;
                }
                _skip_list_level = random_level;
            }

            // create new node with random level generated
            Node<K, V>* inserted_node = create_node(key, value, random_level);

            // insert node
            for (int i = 0; i <= random_level; i++) {
                inserted_node->next[i] = update[i]->next[i];
                update[i]->next[i] = inserted_node;
            }
            std::cout << "Successfully inserted key:" << key << ", value:" << value << std::endl;
            _element_count++;
        }
        mtx.unlock();
        return 0;
    }

    void display_list() {
        std::cout << "\n*****Skip List*****" << "\n";
        for (int i = 0; i <= _skip_list_level; i++) {
            Node<K, V>* node = this->_header->next[i];
            std::cout << "Level " << i << ": ";
            while (node != NULL) {
                std::cout << node->get_key() << ":" << node->get_value() << ";";
                node = node->next[i];
            }
            std::cout << std::endl;
        }
    }

    bool search_element(K key) {
        std::cout << "search_element-----------------" << std::endl;
        Node<K, V>* current = _header;

        // start from highest level of skip list
        for (int i = _skip_list_level; i >= 0; i--) {
            while (current->next[i] && current->next[i]->get_key() < key) {
                current = current->next[i];
            }
        }

        //reached level 0 and advance pointer to right node, which we search
        current = current->next[0];

        // if current node have key equal to searched key, we get it
        if (current and current->get_key() == key) {
            std::cout << "Found key: " << key << ", value: " << current->get_value() << std::endl;
            return true;
        }

        std::cout << "Not Found Key:" << key << std::endl;
        return false;
    }

    void delete_element(K key) {
        mtx.lock();
        Node<K, V>* current = this->_header;
        Node<K, V>* update[_max_level + 1];
        memset(update, 0, sizeof(Node<K, V>*) * (_max_level + 1));

        // start from highest level of skip list
        for (int i = _skip_list_level; i >= 0; i--) {
            while (current->next[i] != NULL && current->next[i]->get_key() < key) {
                current = current->next[i];
            }
            update[i] = current;
        }

        current = current->next[0];
        if (current != NULL && current->get_key() == key) {
            // start for lowest level and delete the current node of each level
            for (int i = 0; i <= _skip_list_level; i++) {
                // if at level i, next node is not target node, break the loop.
                if (update[i]->next[i] != current) break;

                update[i]->next[i] = current->next[i];
            }

            // Remove levels which have no elements
            while (_skip_list_level > 0 && _header->next[_skip_list_level] == 0) {
                _skip_list_level--;
            }

            std::cout << "Successfully deleted key " << key << std::endl;
            delete current;
            _element_count--;
        }
        mtx.unlock();
        return;
    }

    void dump_file() {
        std::cout << "dump_file-----------------" << std::endl;
        _file_writer.open(STORE_FILE);
        Node<K, V>* node = this->_header->next[0];

        while (node != NULL) {
            _file_writer << node->get_key() << ":" << node->get_value() << "\n";
            std::cout << node->get_key() << ":" << node->get_value() << ";\n";
            node = node->next[0];
        }

        _file_writer.flush();
        _file_writer.close();
        return;
    }

    void load_file() {
        _file_reader.open(STORE_FILE);
        std::cout << "load_file-----------------" << std::endl;
        std::string line;
        std::string* key = new std::string();
        std::string* value = new std::string();
        while (getline(_file_reader, line)) {
            get_key_value_from_string(line, key, value);
            if (key->empty() || value->empty()) {
                continue;
            }
            // Define key as int type
            insert_element(stoi(*key), *value);
            std::cout << "key:" << *key << "value:" << *value << std::endl;
        }
        delete key;
        delete value;
        _file_reader.close();
    }

    int size() {
        return _element_count;
    }

private:
    void get_key_value_from_string(const std::string& str, std::string* key, std::string* value) {
        if (!is_valid_string(str)) {
            return;
        }
        *key = str.substr(0, str.find(delimiter));
        *value = str.substr(str.find(delimiter) + 1, str.length());
    }

    bool is_valid_string(const std::string& str) {
        if (str.empty()) {
            return false;
        }
        if (str.find(delimiter) == std::string::npos) {
            return false;
        }
        return true;
    }

    void clear(Node<K, V>* cur) {
        if (cur->next[0] != nullptr) {
            clear(cur->next[0]);
        }
        delete (cur);
    }

private:
    // Maximum level of the skip list
    int _max_level;

    // current level of skip list
    int _skip_list_level;

    // pointer to header node
    Node<K, V>* _header;

    // file operator
    std::ofstream _file_writer;
    std::ifstream _file_reader;

    // skiplist current element count
    int _element_count;
};
// vim: et tw=100 ts=4 sw=4 cc=120