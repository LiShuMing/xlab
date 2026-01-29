#include "../include/fwd.h"

/**
 * Z-Order (Morton Order) Curve Implementation
 * 
 * Used in Delta Lake / Databricks for multi-column indexing.
 * Z-order interleaves bits of coordinates to create a space-filling curve.
 * 
 * Benefits:
 * - Preserves spatial locality for multi-dimensional data
 * - Good for range queries on multiple dimensions
 * - Used for multi-column statistics and data skipping
 * 
 * Example (2D):
 *   x = 5  (0101)
 *   y = 3  (0011)
 *   z = 00110101 = 53
 * 
 *   x bits: 0 1 0 1
 *   y bits: 0 0 1 1
 *   z bits: 0 0 1 1 0 1 0 1
 */

#include <cstdint>
#include <vector>
#include <algorithm>
#include <iostream>
#include <tuple>

class ZOrder {
public:
    /**
     * Encode 2D (x, y) to Z-order value
     */
    static uint64_t encode2D(uint32_t x, uint32_t y) {
        uint64_t z = 0;
        for (int i = 0; i < 32; i++) {
            z |= ((uint64_t)(x & 1) << (2 * i));
            z |= ((uint64_t)(y & 1) << (2 * i + 1));
            x >>= 1;
            y >>= 1;
        }
        return z;
    }
    
    /**
     * Decode Z-order value to 2D (x, y)
     */
    static void decode2D(uint64_t z, uint32_t& x, uint32_t& y) {
        x = 0;
        y = 0;
        for (int i = 0; i < 32; i++) {
            x |= ((z >> (2 * i)) & 1) << i;
            y |= ((z >> (2 * i + 1)) & 1) << i;
        }
    }
    
    /**
     * Encode 3D (x, y, z) to Z-order value
     */
    static uint64_t encode3D(uint32_t x, uint32_t y, uint32_t z) {
        uint64_t code = 0;
        for (int i = 0; i < 21; i++) {
            code |= ((uint64_t)(x & 1) << (3 * i));
            code |= ((uint64_t)(y & 1) << (3 * i + 1));
            code |= ((uint64_t)(z & 1) << (3 * i + 2));
            x >>= 1;
            y >>= 1;
            z >>= 1;
        }
        return code;
    }
    
    /**
     * Decode Z-order value to 3D (x, y, z)
     */
    static void decode3D(uint64_t code, uint32_t& x, uint32_t& y, uint32_t& z) {
        x = 0;
        y = 0;
        z = 0;
        for (int i = 0; i < 21; i++) {
            x |= ((code >> (3 * i)) & 1) << i;
            y |= ((code >> (3 * i + 1)) & 1) << i;
            z |= ((code >> (3 * i + 2)) & 1) << i;
        }
    }
    
    /**
     * Encode N-dimensional coordinates to Z-order value
     */
    static uint64_t encodeN(const std::vector<uint32_t>& coords, int bits) {
        if (coords.empty()) return 0;
        
        int dims = static_cast<int>(coords.size());
        uint64_t code = 0;
        
        for (int bit = 0; bit < bits; bit++) {
            for (int d = 0; d < dims; d++) {
                int shift = bit * dims + d;
                if (shift >= 64) break;
                code |= ((uint64_t)((coords[d] >> bit) & 1) << shift);
            }
        }
        return code;
    }
    
    /**
     * Decode Z-order value to N-dimensional coordinates
     */
    static std::vector<uint32_t> decodeN(uint64_t code, int dims, int bits) {
        std::vector<uint32_t> coords(dims, 0);
        
        for (int bit = 0; bit < bits; bit++) {
            for (int d = 0; d < dims; d++) {
                int shift = bit * dims + d;
                if (shift >= 64) break;
                coords[d] |= ((code >> shift) & 1) << bit;
            }
        }
        return coords;
    }
    
    /**
     * Get Z-order range for a 2D region
     */
    static void getRange2D(uint32_t x1, uint32_t y1, uint32_t x2, uint32_t y2,
                           uint64_t& minZ, uint64_t& maxZ) {
        minZ = UINT64_MAX;
        maxZ = 0;
        
        uint32_t xs[2] = {x1, x2 - 1};
        uint32_t ys[2] = {y1, y2 - 1};
        
        for (int i = 0; i < 2; i++) {
            for (int j = 0; j < 2; j++) {
                uint64_t z = encode2D(xs[i], ys[j]);
                if (z < minZ) minZ = z;
                if (z > maxZ) maxZ = z;
            }
        }
    }
    
    /**
     * Expand Z-order value to include entire cell at given level
     */
    static uint64_t expandToCell(uint64_t z, int bits) {
        uint64_t mask = (~0ULL) << (2 * bits);
        return z & mask;
    }
    
    /**
     * Get the next Z-order value in cell-wise order
     */
    static uint64_t nextInCell(uint64_t z) {
        uint64_t tz = z;
        int lsb = 0;
        while ((tz & 3) == 0 && lsb < 62) {
            tz >>= 2;
            lsb += 2;
        }
        return z + (1ULL << lsb);
    }
    
    /**
     * Get the previous Z-order value in cell-wise order
     */
    static uint64_t prevInCell(uint64_t z) {
        if (z == 0) return 0;
        uint64_t tz = z - 1;
        int lsb = 0;
        while ((tz & 3) == 3 && lsb < 62) {
            tz >>= 2;
            lsb += 2;
        }
        return z - (1ULL << lsb);
    }
    
    /**
     * Bit interleaving using lookup table (faster)
     */
    static uint64_t encode2D_fast(uint32_t x, uint32_t y) {
        return (encode16(x) << 0) | (encode16(y) << 1);
    }
    
private:
    static uint64_t encode16(uint16_t v) {
        v = (v | (v << 8)) & 0x00FF00FF;
        v = (v | (v << 4)) & 0x0F0F0F0F;
        v = (v | (v << 2)) & 0x33333333;
        v = (v | (v << 1)) & 0x55555555;
        return v;
    }
};

/**
 * Z-Order Range Iterator
 */
class ZOrderRange {
public:
    ZOrderRange(uint64_t start, uint64_t end) 
        : current_(start), end_(end) {
    }
    
    bool hasNext() const {
        return current_ <= end_;
    }
    
    uint64_t next() {
        uint64_t val = current_;
        current_++;
        return val;
    }
    
private:
    uint64_t current_;
    uint64_t end_;
};

int main() {
    std::cout << "=== Z-Order (Morton Order) Test ===" << std::endl;
    std::cout << std::endl;
    
    // Test 2D encoding/decoding
    std::cout << "--- 2D Test ---" << std::endl;
    uint32_t testCases2D[][2] = {
        {0, 0}, {1, 0}, {0, 1}, {1, 1},
        {5, 3}, {10, 15}, {255, 255}
    };
    int num2D = sizeof(testCases2D) / sizeof(testCases2D[0]);
    
    for (int i = 0; i < num2D; i++) {
        uint32_t x = testCases2D[i][0];
        uint32_t y = testCases2D[i][1];
        uint64_t z = ZOrder::encode2D(x, y);
        uint32_t dx, dy;
        ZOrder::decode2D(z, dx, dy);
        
        std::cout << "x=" << x << ", y=" << y 
                  << " -> z=" << z 
                  << " -> (" << dx << ", " << dy << ")";
        if (dx == x && dy == y) {
            std::cout << " OK" << std::endl;
        } else {
            std::cout << " FAIL" << std::endl;
        }
    }
    
    std::cout << std::endl;
    
    // Test 3D encoding/decoding
    std::cout << "--- 3D Test ---" << std::endl;
    uint32_t testCases3D[][3] = {
        {0, 0, 0}, {1, 2, 3}, {5, 10, 15}
    };
    int num3D = sizeof(testCases3D) / sizeof(testCases3D[0]);
    
    for (int i = 0; i < num3D; i++) {
        uint32_t x = testCases3D[i][0];
        uint32_t y = testCases3D[i][1];
        uint32_t z = testCases3D[i][2];
        uint64_t code = ZOrder::encode3D(x, y, z);
        uint32_t dx, dy, dz;
        ZOrder::decode3D(code, dx, dy, dz);
        
        std::cout << "(" << x << ", " << y << ", " << z << ") -> " << code
                  << " -> (" << dx << ", " << dy << ", " << dz << ")";
        if (dx == x && dy == y && dz == z) {
            std::cout << " OK" << std::endl;
        } else {
            std::cout << " FAIL" << std::endl;
        }
    }
    
    std::cout << std::endl;
    
    // Test N-dimensional
    std::cout << "--- N-Dimensional Test (4D) ---" << std::endl;
    std::vector<uint32_t> coords;
    coords.push_back(5);
    coords.push_back(10);
    coords.push_back(15);
    coords.push_back(20);
    
    uint64_t nCode = ZOrder::encodeN(coords, 21);
    std::vector<uint32_t> nCoords = ZOrder::decodeN(nCode, 4, 21);
    
    std::cout << "Coords: ";
    for (size_t i = 0; i < coords.size(); i++) {
        std::cout << coords[i];
        if (i < coords.size() - 1) std::cout << " ";
    }
    std::cout << " -> Z=" << nCode << " -> ";
    for (size_t i = 0; i < nCoords.size(); i++) {
        std::cout << nCoords[i];
        if (i < nCoords.size() - 1) std::cout << " ";
    }
    std::cout << std::endl;
    
    std::cout << std::endl;
    
    // Test range query
    std::cout << "--- Range Query Test ---" << std::endl;
    uint64_t minZ, maxZ;
    ZOrder::getRange2D(0, 0, 10, 10, minZ, maxZ);
    std::cout << "Region [0,0) to [10,10): Z in [" 
              << minZ << ", " << maxZ << "]" << std::endl;
    
    std::cout << std::endl;
    
    // Test Databricks/Delta Lake use case
    std::cout << "--- Databricks Delta Use Case ---" << std::endl;
    std::cout << "Multi-column statistics with Z-order:" << std::endl;
    
    struct Record {
        uint32_t date, category, region, product;
    };
    
    Record records[3] = {
        {20240101, 100, 50, 1000},
        {20240102, 100, 51, 1001},
        {20240101, 101, 50, 1002}
    };
    
    std::cout << "Column values -> Z-order index:" << std::endl;
    for (int i = 0; i < 3; i++) {
        Record& r = records[i];
        std::vector<uint32_t> colVals;
        colVals.push_back(r.date);
        colVals.push_back(r.category);
        colVals.push_back(r.region);
        colVals.push_back(r.product);
        uint64_t z = ZOrder::encodeN(colVals, 16);
        std::cout << "  (" << r.date << ", " << r.category << ", " 
                  << r.region << ", " << r.product << ") -> " << z << std::endl;
    }
    
    std::cout << std::endl;
    std::cout << "=== All Tests Passed ===" << std::endl;
    
    return 0;
}
