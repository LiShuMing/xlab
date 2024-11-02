#pragma once

#include <stdio.h>
#include <set>
#include <string>
#include <map>

class ConsistentHash {
private:
	// key: hash, value: ip
    std::map<uint32_t, std::string> serverNodes;
	// ip set
    std::set<std::string> physicalNodes; 
	// virtual node num for each machine
    int virtualNodeNum; 
public:
    ConsistentHash(int virtualNodeNum) : virtualNodeNum(virtualNodeNum){
		// default: 4 maichine
        physicalNodes.insert(std::string("192.168.1.101"));
        physicalNodes.insert(std::string("192.168.1.102"));
        physicalNodes.insert(std::string("192.168.1.103"));
        physicalNodes.insert(std::string("192.168.1.104"));
    };

    ~ConsistentHash() {
        serverNodes.clear();
    };

    static uint32_t FNVHash(std::string key);
    void Initialize();
    void AddNewPhysicalNode(const std::string& nodeIp);
    void DeletePhysicalNode(const std::string& nodeIp);
    std::string GetServerIndex(const std::string& key);
    void StatisticPerf(std::string& label, int left, int right);
};
