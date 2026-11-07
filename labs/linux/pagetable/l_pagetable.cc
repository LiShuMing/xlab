/**
 * Page Table Walk and TLB Simulator
 *
 * Simulates virtual-to-physical address translation with:
 * - Multi-level page tables (4-level or 5-level for x86-64)
 * - TLB with LRU replacement policy
 * - Access cost calculation
 * - Support for huge pages
 *
 * Key insights demonstrated:
 * 1. Why multi-level page tables (sparse address space)
 * 2. Why TLB is critical (page table walk is expensive)
 * 3. Why huge pages are beneficial (fewer walk levels, less TLB pressure)
 */

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unordered_map>
#include <list>
#include <vector>
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <sstream>

// ============================================================================
// Configuration
// ============================================================================

// Page table entry flags
constexpr uint64_t PTE_PRESENT = 1ULL << 0;      // Page present
constexpr uint64_t PTE_WRITE = 1ULL << 1;       // Writable
constexpr uint64_t PTE_USER = 1ULL << 2;        // User accessible
constexpr uint64_t PTE_HUGE = 1ULL << 7;        // Huge page (2MB or 1GB)

// x86-64 page table constants
constexpr size_t PAGE_SIZE_4KB = 4096;
constexpr size_t PAGE_SIZE_2MB = 2 * 1024 * 1024;
constexpr size_t PAGE_SIZE_1GB = 1024 * 1024 * 1024;
constexpr size_t PTE_SIZE = 8;  // 8 bytes per PTE
constexpr size_t ENTRIES_PER_PAGE = PAGE_SIZE_4KB / PTE_SIZE;  // 512 entries

// Address space constants
constexpr int VA_BITS = 48;  // 48-bit virtual address
constexpr int PA_BITS = 52;  // 52-bit physical address (typical)

// ============================================================================
// Page Table Entry
// ============================================================================

struct PageTableEntry {
    uint64_t pfn : 40;      // Physical frame number (40 bits)
    uint64_t flags : 12;    // Page flags
    uint64_t reserved : 12; // Reserved bits

    PageTableEntry() : pfn(0), flags(0), reserved(0) {}

    bool is_present() const { return flags & PTE_PRESENT; }
    bool is_huge() const { return flags & PTE_HUGE; }
    void set_present() { flags |= PTE_PRESENT; }
    void set_huge() { flags |= PTE_HUGE; }
};

// ============================================================================
// Page Table
// ============================================================================

class PageTable {
public:
    enum class Level {
        P4 = 0,  // Page-Map Level 4 (or PML5 for 5-level)
        P3 = 1,  // Page-Directory-Pointer Table
        P2 = 2,  // Page Directory
        P1 = 3,  // Page Table
        P0 = 4   // For 5-level paging
    };

private:
    int levels_;  // 4 or 5
    size_t page_size_;
    std::unordered_map<uint64_t, PageTableEntry*> tables_;  // Virtual address -> PTE array

    // Allocate a new page table
    PageTableEntry* allocate_table() {
        PageTableEntry* table = new PageTableEntry[ENTRIES_PER_PAGE];
        return table;
    }

    // Get or create a page table at given level and index
    PageTableEntry* get_or_create_table(uint64_t base_addr, Level level, size_t index) {
        uint64_t table_addr = base_addr + (static_cast<uint64_t>(level) << 40) + index;
        auto it = tables_.find(table_addr);
        if (it != tables_.end()) {
            return it->second;
        }
        PageTableEntry* table = allocate_table();
        tables_[table_addr] = table;
        return table;
    }

    // Extract index from virtual address for given level
    // x86-64 4-level: bits 47:39 (PML4), 38:30 (PDPT), 29:21 (PD), 20:12 (PT)
    // x86-64 5-level: bits 56:48 (PML5), 47:39 (PML4), 38:30 (PDPT), 29:21 (PD), 20:12 (PT)
    size_t extract_index(uint64_t va, Level level) const {
        int shift;
        int level_num = static_cast<int>(level);
        if (levels_ == 5) {
            // 5-level: P4(0)=48, P3(1)=39, P2(2)=30, P1(3)=21, P0(4)=12
            shift = 48 - level_num * 9;
        } else {
            // 4-level: P3(0)=39, P2(1)=30, P1(2)=21, P0(3)=12
            shift = 39 - level_num * 9;
        }
        return (va >> shift) & 0x1FF;  // 9 bits = 512 entries
    }

public:
    PageTable(int levels, size_t page_size) : levels_(levels), page_size_(page_size) {
        if (levels != 4 && levels != 5) {
            fprintf(stderr, "Error: Only 4 or 5 level paging supported\n");
            exit(1);
        }
    }

    ~PageTable() {
        for (auto& pair : tables_) {
            delete[] pair.second;
        }
    }

    // Walk page table and return translation result
    struct WalkResult {
        bool success;
        uint64_t pfn;
        std::vector<size_t> indices;  // Indices at each level
        int walk_cost;  // Number of memory accesses
        bool is_huge_page;
        size_t huge_page_size;
    };

    WalkResult walk(uint64_t va) {
        WalkResult result;
        result.success = false;
        result.walk_cost = 0;
        result.is_huge_page = false;
        result.huge_page_size = page_size_;

        // Start from top level
        Level start_level = (levels_ == 5) ? Level::P4 : Level::P3;
        uint64_t base_addr = 0;  // Root page table address (simplified)

        PageTableEntry* current_table = get_or_create_table(base_addr, start_level, 0);
        result.walk_cost++;  // Access root table

        // Walk through levels
        for (int i = 0; i < levels_; ++i) {
            Level level = static_cast<Level>(static_cast<int>(start_level) + i);
            size_t index = extract_index(va, level);
            result.indices.push_back(index);

            PageTableEntry& pte = current_table[index];
            result.walk_cost++;  // Access PTE

            if (!pte.is_present()) {
                // Page not present - would trigger page fault in real system
                return result;
            }

            // Check for huge page
            if (pte.is_huge()) {
                result.is_huge_page = true;
                // Determine huge page size based on level
                if (level == Level::P2) {
                    result.huge_page_size = PAGE_SIZE_2MB;
                } else if (level == Level::P3) {
                    result.huge_page_size = PAGE_SIZE_1GB;
                }
                result.pfn = pte.pfn;
                result.success = true;
                return result;
            }

            // If not last level, continue to next level
            if (i < levels_ - 1) {
                uint64_t next_table_addr = pte.pfn * (PAGE_SIZE_4KB / PTE_SIZE);
                current_table = get_or_create_table(next_table_addr, 
                    static_cast<Level>(static_cast<int>(level) + 1), 0);
                result.walk_cost++;  // Access next level table
            } else {
                // Last level - this is the final PTE
                result.pfn = pte.pfn;
                result.success = true;
            }
        }

        return result;
    }

    // Create a mapping by walking and creating the full path
    void create_mapping(uint64_t va, uint64_t pfn, bool huge = false, Level huge_level = Level::P1) {
        Level start_level = (levels_ == 5) ? Level::P4 : Level::P3;
        uint64_t base_addr = 0;
        uint64_t next_pfn = 1;  // Start allocating PFNs from 1

        PageTableEntry* current_table = get_or_create_table(base_addr, start_level, 0);

        // Walk through levels, creating tables as needed
        for (int i = 0; i < levels_; ++i) {
            Level level = static_cast<Level>(static_cast<int>(start_level) + i);
            size_t index = extract_index(va, level);

            PageTableEntry& pte = current_table[index];

            // Check if this should be a huge page
            if (huge && level == huge_level) {
                pte.pfn = pfn;
                pte.set_present();
                pte.set_huge();
                return;
            }

            // If not last level, create next level table if needed
            if (i < levels_ - 1) {
                if (!pte.is_present()) {
                    // Allocate a new page table
                    uint64_t table_pfn = next_pfn++;
                    pte.pfn = table_pfn;
                    pte.set_present();
                }
                uint64_t next_table_addr = pte.pfn * (PAGE_SIZE_4KB / PTE_SIZE);
                current_table = get_or_create_table(next_table_addr, 
                    static_cast<Level>(static_cast<int>(level) + 1), 0);
            } else {
                // Last level - set the final PTE
                pte.pfn = pfn;
                pte.set_present();
            }
        }
    }
};

// ============================================================================
// TLB Entry
// ============================================================================

struct TLBEntry {
    uint64_t vpn;      // Virtual page number
    uint64_t pfn;      // Physical frame number
    bool is_huge;
    size_t huge_page_size;
    uint64_t access_time;  // For LRU

    TLBEntry() : vpn(0), pfn(0), is_huge(false), huge_page_size(PAGE_SIZE_4KB), access_time(0) {}
};

// ============================================================================
// TLB with LRU Replacement
// ============================================================================

class TLB {
private:
    size_t size_;
    std::unordered_map<uint64_t, TLBEntry> entries_;
    uint64_t access_counter_;

    // Find LRU entry to evict
    uint64_t find_lru_vpn() const {
        uint64_t lru_vpn = 0;
        uint64_t min_time = UINT64_MAX;

        for (const auto& pair : entries_) {
            if (pair.second.access_time < min_time) {
                min_time = pair.second.access_time;
                lru_vpn = pair.first;
            }
        }
        return lru_vpn;
    }

public:
    TLB(size_t size) : size_(size), access_counter_(0) {}

    struct LookupResult {
        bool hit;
        uint64_t pfn;
        int cost;  // Access cost (1 for hit, walk_cost for miss)
    };

    LookupResult lookup(uint64_t vpn, const PageTable::WalkResult& walk_result) {
        LookupResult result;
        result.cost = 0;

        auto it = entries_.find(vpn);
        if (it != entries_.end()) {
            // TLB hit
            result.hit = true;
            result.pfn = it->second.pfn;
            result.cost = 1;  // 1 memory access for TLB lookup
            it->second.access_time = ++access_counter_;
        } else {
            // TLB miss - need page table walk
            result.hit = false;
            if (walk_result.success) {
                result.pfn = walk_result.pfn;
                result.cost = walk_result.walk_cost;  // Cost of page table walk

                // Insert into TLB (evict LRU if full)
                if (entries_.size() >= size_) {
                    uint64_t lru_vpn = find_lru_vpn();
                    entries_.erase(lru_vpn);
                }

                TLBEntry entry;
                entry.vpn = vpn;
                entry.pfn = walk_result.pfn;
                entry.is_huge = walk_result.is_huge_page;
                entry.huge_page_size = walk_result.huge_page_size;
                entry.access_time = ++access_counter_;
                entries_[vpn] = entry;
            } else {
                result.pfn = 0;
                result.cost = walk_result.walk_cost;  // Still pay walk cost even if failed
            }
        }

        return result;
    }

    void clear() {
        entries_.clear();
        access_counter_ = 0;
    }

    size_t size() const { return entries_.size(); }
    size_t capacity() const { return size_; }
};

// ============================================================================
// Address Translation Simulator
// ============================================================================

class AddressTranslator {
private:
    PageTable page_table_;
    TLB tlb_;
    size_t page_size_;
    int levels_;

    // Extract VPN from virtual address
    uint64_t extract_vpn(uint64_t va) const {
        return va / page_size_;
    }

    // Extract page offset
    uint64_t extract_offset(uint64_t va) const {
        return va % page_size_;
    }

public:
    AddressTranslator(int levels, size_t page_size, size_t tlb_size)
        : page_table_(levels, page_size), tlb_(tlb_size), page_size_(page_size), levels_(levels) {}

    struct TranslationResult {
        uint64_t va;
        uint64_t pa;
        bool tlb_hit;
        int total_cost;
        std::vector<size_t> page_table_indices;
        bool is_huge_page;
        size_t huge_page_size;
    };

    TranslationResult translate(uint64_t va) {
        TranslationResult result;
        result.va = va;
        result.tlb_hit = false;
        result.total_cost = 0;
        result.is_huge_page = false;
        result.huge_page_size = page_size_;

        // Walk page table first to determine if it's a huge page
        PageTable::WalkResult walk_result = page_table_.walk(va);
        result.page_table_indices = walk_result.indices;
        result.is_huge_page = walk_result.is_huge_page;
        result.huge_page_size = walk_result.huge_page_size;

        // Extract VPN and offset based on actual page size
        uint64_t vpn = va / result.huge_page_size;
        uint64_t offset = va % result.huge_page_size;

        // Check TLB
        TLB::LookupResult tlb_result = tlb_.lookup(vpn, walk_result);
        result.tlb_hit = tlb_result.hit;
        result.total_cost = tlb_result.cost;

        // Calculate physical address
        if (walk_result.success) {
            uint64_t pfn = tlb_result.pfn;
            result.pa = (pfn * result.huge_page_size) + offset;
        } else {
            result.pa = 0;  // Page fault
        }

        return result;
    }

    void create_mapping(uint64_t va, uint64_t pfn, bool huge = false, bool huge_1gb = false) {
        if (huge) {
            PageTable::Level huge_level = huge_1gb ? PageTable::Level::P3 : PageTable::Level::P2;
            page_table_.create_mapping(va, pfn, true, huge_level);
        } else {
            page_table_.create_mapping(va, pfn, false, PageTable::Level::P1);
        }
    }

    void clear_tlb() { tlb_.clear(); }
    size_t tlb_size() const { return tlb_.size(); }
    size_t tlb_capacity() const { return tlb_.capacity(); }
};

// ============================================================================
// Utility Functions
// ============================================================================

void print_hex(uint64_t value, int bits) {
    int hex_digits = (bits + 3) / 4;
    printf("0x%0*llx", hex_digits, static_cast<unsigned long long>(value));
}

void print_translation_result(const AddressTranslator::TranslationResult& result, int va_bits) {
    printf("Virtual Address: ");
    print_hex(result.va, va_bits);
    printf("\n");

    printf("Page Table Walk:\n");
    for (size_t i = 0; i < result.page_table_indices.size(); ++i) {
        printf("  Level %zu: index = %zu\n", i, result.page_table_indices[i]);
    }

    if (result.is_huge_page) {
        printf("  Huge Page: %zu bytes\n", result.huge_page_size);
    }

    printf("TLB: %s\n", result.tlb_hit ? "HIT" : "MISS");
    printf("Access Cost: %d memory accesses\n", result.total_cost);

    if (result.pa != 0) {
        printf("Physical Address: ");
        print_hex(result.pa, PA_BITS);
        printf("\n");
    } else {
        printf("Physical Address: PAGE FAULT (not mapped)\n");
    }
    printf("\n");
}

void print_statistics(const std::vector<AddressTranslator::TranslationResult>& results) {
    size_t tlb_hits = 0;
    size_t tlb_misses = 0;
    uint64_t total_cost = 0;
    uint64_t cost_with_tlb_hit = 0;
    uint64_t cost_with_tlb_miss = 0;

    for (const auto& result : results) {
        if (result.tlb_hit) {
            tlb_hits++;
            cost_with_tlb_hit += result.total_cost;
        } else {
            tlb_misses++;
            cost_with_tlb_miss += result.total_cost;
        }
        total_cost += result.total_cost;
    }

    printf("================================================================================\n");
    printf("Translation Statistics\n");
    printf("================================================================================\n");
    printf("Total translations: %zu\n", results.size());
    printf("TLB hits: %zu (%.2f%%)\n", tlb_hits, 
           100.0 * tlb_hits / results.size());
    printf("TLB misses: %zu (%.2f%%)\n", tlb_misses,
           100.0 * tlb_misses / results.size());
    printf("\n");
    printf("Total access cost: %llu memory accesses\n", 
           static_cast<unsigned long long>(total_cost));
    if (tlb_hits > 0) {
        printf("Average cost (TLB hit): %.2f accesses\n",
               static_cast<double>(cost_with_tlb_hit) / tlb_hits);
    }
    if (tlb_misses > 0) {
        printf("Average cost (TLB miss): %.2f accesses\n",
               static_cast<double>(cost_with_tlb_miss) / tlb_misses);
    }
    printf("Average cost (overall): %.2f accesses\n",
           static_cast<double>(total_cost) / results.size());
    printf("================================================================================\n");
}

// ============================================================================
// Main
// ============================================================================

void print_usage(const char* prog_name) {
    printf("Usage: %s [options]\n", prog_name);
    printf("\n");
    printf("Options:\n");
    printf("  --levels N        Number of page table levels (4 or 5, default: 4)\n");
    printf("  --page-size N     Page size in bytes (4096, 2097152, 1073741824, default: 4096)\n");
    printf("  --tlb-size N      TLB size in entries (default: 64)\n");
    printf("  --va ADDR         Virtual address to translate (hex, e.g., 0x12345678)\n");
    printf("  --benchmark       Run benchmark with multiple addresses\n");
    printf("  --huge-page       Demonstrate huge page (2MB) benefits\n");
    printf("  --help            Show this help message\n");
    printf("\n");
    printf("Examples:\n");
    printf("  %s --va 0x12345678\n", prog_name);
    printf("  %s --levels 5 --page-size 4096 --tlb-size 128 --va 0x7fff12345678\n", prog_name);
    printf("  %s --benchmark\n", prog_name);
}

int main(int argc, char* argv[]) {
    // Default configuration
    int levels = 4;
    size_t page_size = PAGE_SIZE_4KB;
    size_t tlb_size = 64;
    uint64_t va = 0;
    bool benchmark_mode = false;
    bool huge_page_demo = false;

    // Parse arguments
    for (int i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--levels") == 0 && i + 1 < argc) {
            levels = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--page-size") == 0 && i + 1 < argc) {
            page_size = strtoull(argv[++i], nullptr, 0);
        } else if (strcmp(argv[i], "--tlb-size") == 0 && i + 1 < argc) {
            tlb_size = strtoull(argv[++i], nullptr, 0);
        } else if (strcmp(argv[i], "--va") == 0 && i + 1 < argc) {
            va = strtoull(argv[++i], nullptr, 0);
        } else if (strcmp(argv[i], "--benchmark") == 0) {
            benchmark_mode = true;
        } else if (strcmp(argv[i], "--huge-page") == 0) {
            huge_page_demo = true;
        } else if (strcmp(argv[i], "--help") == 0) {
            print_usage(argv[0]);
            return 0;
        }
    }

    printf("================================================================================\n");
    printf("Page Table Walk and TLB Simulator\n");
    printf("================================================================================\n");
    printf("Configuration:\n");
    printf("  Page table levels: %d\n", levels);
    printf("  Page size: %zu bytes (%zu KB)\n", page_size, page_size / 1024);
    printf("  TLB size: %zu entries\n", tlb_size);
    printf("  Virtual address bits: %d\n", VA_BITS);
    printf("  Physical address bits: %d\n", PA_BITS);
    printf("================================================================================\n\n");

    AddressTranslator translator(levels, page_size, tlb_size);

    if (benchmark_mode) {
        // Benchmark mode: test multiple addresses
        std::vector<AddressTranslator::TranslationResult> results;
        
        // Test addresses with different patterns
        uint64_t test_addresses[] = {
            0x0000000000001000,
            0x0000000000100000,
            0x0000000010000000,
            0x00007fff12345678,
            0x00007fff12345678,  // Same address (should TLB hit)
            0x00007fff12346678,  // Same page (should TLB hit)
            0x00007fff12350000,  // Different page (likely TLB miss)
            0x00007fff12450000,  // Different page
            0x00007fff20000000,  // Far away
        };

        // Create mappings for test addresses
        printf("Creating page table mappings...\n");
        uint64_t pfn_counter = 100;  // Start PFN from 100
        for (size_t i = 0; i < sizeof(test_addresses) / sizeof(test_addresses[0]); ++i) {
            uint64_t vpn = test_addresses[i] / page_size;
            translator.create_mapping(test_addresses[i], pfn_counter + vpn, false);
        }
        printf("\n");

        printf("Running benchmark with %zu addresses...\n\n", 
               sizeof(test_addresses) / sizeof(test_addresses[0]));

        for (size_t i = 0; i < sizeof(test_addresses) / sizeof(test_addresses[0]); ++i) {
            printf("--- Translation %zu ---\n", i + 1);
            auto result = translator.translate(test_addresses[i]);
            results.push_back(result);
            print_translation_result(result, VA_BITS);
        }

        print_statistics(results);
    } else if (huge_page_demo) {
        // Demonstrate huge page benefits
        printf("Demonstrating Huge Page Benefits\n");
        printf("================================================================================\n\n");
        
        uint64_t test_va = 0x000010000000;
        
        // Test with 4KB pages
        printf("--- 4KB Page (Normal) ---\n");
        AddressTranslator translator_4k(levels, PAGE_SIZE_4KB, tlb_size);
        uint64_t vpn_4k = test_va / PAGE_SIZE_4KB;
        translator_4k.create_mapping(test_va, 100 + vpn_4k, false);
        auto result_4k = translator_4k.translate(test_va);
        print_translation_result(result_4k, VA_BITS);
        
        // Test with 2MB huge pages
        printf("--- 2MB Huge Page ---\n");
        AddressTranslator translator_2m(levels, PAGE_SIZE_4KB, tlb_size);
        uint64_t vpn_2m = test_va / PAGE_SIZE_2MB;
        translator_2m.create_mapping(test_va, 200 + vpn_2m, true, false);
        auto result_2m = translator_2m.translate(test_va);
        print_translation_result(result_2m, VA_BITS);
        
        printf("Key Insight: Huge pages reduce page table walk from %d to %d levels,\n",
               static_cast<int>(result_4k.page_table_indices.size()),
               static_cast<int>(result_2m.page_table_indices.size()));
        printf("reducing access cost from %d to %d memory accesses!\n",
               result_4k.total_cost, result_2m.total_cost);
        printf("This also reduces TLB pressure since one TLB entry covers 2MB instead of 4KB.\n");
    } else if (va != 0) {
        // Single address translation - create a mapping first
        uint64_t vpn = va / page_size;
        translator.create_mapping(va, 100 + vpn, false);
        
        auto result = translator.translate(va);
        print_translation_result(result, VA_BITS);
    } else {
        // Interactive mode or show usage
        printf("No virtual address specified. Use --va ADDR or --benchmark\n");
        printf("Run with --help for usage information.\n");
        return 1;
    }

    return 0;
}
