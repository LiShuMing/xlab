#include "common/consistent_hash/consistent_hash.h"

#include <iostream>
#include <map>
#include <sstream>
#include <string>

// 32-bit Fowler-Noll-Vo hash func
// https://en.wikipedia.org/wiki/Fowler–Noll–Vo_hash_function
uint32_t ConsistentHash::FNVHash(const std::string& key) {
    const int p = 16777619;
    uint32_t hash = 2166136261;
    for (int idx = 0; idx < key.size(); ++idx) {
        hash = (hash ^ key[idx]) * p;
    }
    hash += hash << 13;
    hash ^= hash >> 7;
    hash += hash << 3;
    hash ^= hash >> 17;
    hash += hash << 5;
    if (hash < 0) {
        hash = -hash;
    }
    return hash;
}

void ConsistentHash::Initialize() {
    for (auto& ip : physicalNodes) {
        for (int j = 0; j < virtualNodeNum; ++j) {
            std::stringstream nodeKey;
            nodeKey << ip << "#" << j;
            uint32_t partition = FNVHash(nodeKey.str());
            serverNodes.insert({partition, ip});
        }
    }
}

uint32_t ConsistentHash::_GetHash(const std::string& nodeIp, int idx) {
    // std::stringstream nodeKey;
    // nodeKey << nodeIp << "#" << j;
    return FNVHash(nodeIp + "#" + std::to_string(idx));
}

void ConsistentHash::AddNewPhysicalNode(const std::string& nodeIp) {
    for (int j = 0; j < virtualNodeNum; ++j) {
        uint32_t partition = _GetHash(nodeIp, j);
        serverNodes.insert({partition, nodeIp});
    }
}

void ConsistentHash::DeletePhysicalNode(const std::string& nodeIp) {
    for (int j = 0; j < virtualNodeNum; ++j) {
        uint32_t partition = _GetHash(nodeIp, j);
        serverNodes.insert({partition, nodeIp});
        auto it = serverNodes.find(partition);
        if (it != serverNodes.end()) {
            serverNodes.erase(it);
        }
    }
}

std::string ConsistentHash::GetServerIndex(const std::string& key) {
    uint32_t partition = FNVHash(key);
    auto it = serverNodes.lower_bound(partition);
    if (it == serverNodes.end()) {
        if (serverNodes.empty()) {
            std::cout << "no available nodes" << '\n';
        }
        return serverNodes.begin()->second;
    }
    return it->second;
}

void ConsistentHash::StatisticPerf(const std::string& label, int objMin, int objMax) {
    std::map<std::string, int> cnt;
    for (int i = objMin; i <= objMax; i++) {
        std::string nodeIp = GetServerIndex(std::to_string(i));
        cnt[nodeIp]++;
    }
    int total = objMax - objMin + 1;
    std::cout << "==== " << label << " ====" << '\n';
    for (auto& p : cnt) {
        std::cout << "nodeIp: " << p.first << " rate: " << 100 * p.second / (total * 1.0) << "%"
                  << '\n';
    }
}
