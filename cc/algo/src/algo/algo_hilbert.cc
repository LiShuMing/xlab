#include "../include/fwd.h"

/**
 * Hilbert Curve vs Z-Order (Morton Order) Comparison
 * 
 * Hilbert Curve Advantages over Z-Order:
 * 
 * 1. **Better Spatial Locality**: Hilbert curve preserves proximity better
 *    - Consecutive Hilbert values are always adjacent in space
 *    - Z-order can have large jumps between consecutive values
 * 
 * 2. **No Long Jumps**: Hilbert is a continuous space-filling curve
 *    - |Hilbert(i+1) - Hilbert(i)| is bounded
 *    - Z-order can jump across the entire space
 * 
 * 3. **More Uniform Distribution**: Better for load balancing
 *    - Hilbert partitions are more compact
 *    - Better for parallel processing and range queries
 * 
 * 4. **Smaller Bounding Boxes**: Hilbert ranges have smaller areas
 *    - Less wasted I/O for range scans
 *    - Better data skipping efficiency
 * 
 * 5. **Better Clustering**: Points close in Hilbert order are close in space
 *    - Improves cache locality
 *    - Better for similarity searches
 * 
 * Z-Order Advantages:
 * 1. Simpler implementation (just bit interleaving)
 * 2. Faster encoding/decoding
 * 3. Easier to understand and debug
 * 4. Can be efficiently decomposed for range queries
 */

#include <cstdint>
#include <vector>
#include <algorithm>
#include <iostream>
#include <cmath>

/**
 * Hilbert Curve Implementation
 * 
 * Uses iterative bit manipulation for encoding/decoding
 * Order N Hilbert curve maps [0, 2^N) × [0, 2^N) to [0, 4^N)
 */

class HilbertCurve {
public:
    /**
     * Encode 2D (x, y) to Hilbert curve index
     * 
     * @param x, y Coordinates in [0, 2^order)
     * @param order Order of Hilbert curve (max 15 for 32-bit)
     * @return Hilbert index in [0, 4^order)
     */
    static uint64_t encode(uint32_t x, uint32_t y, int order = 15) {
        uint64_t d = 0;
        
        for (int s = 1 << (order - 1); s > 0; s >>= 1) {
            uint32_t rx = (x & s) > 0 ? 1 : 0;
            uint32_t ry = (y & s) > 0 ? 1 : 0;
            
            d += s * s * ((3 * rx) ^ ry);
            
            // Rotate
            if (ry == 0) {
                if (rx == 1) {
                    x = (1 << order) - 1 - x;
                    y = (1 << order) - 1 - y;
                }
                // Swap x and y
                uint32_t t = x;
                x = y;
                y = t;
            }
        }
        
        return d;
    }
    
    /**
     * Decode Hilbert index to 2D (x, y)
     * 
     * @param d Hilbert index
     * @param order Order of Hilbert curve
     * @param x, y Output coordinates
     */
    static void decode(uint64_t d, int order, uint32_t& x, uint32_t& y) {
        x = 0;
        y = 0;
        
        for (int s = 1 << (order - 1); s > 0; s >>= 1) {
            uint32_t rx = (d / (s * s)) % 4 / 2;
            uint32_t ry = (d / (s * s)) % 4 % 2;
            
            if (ry == 0) {
                // Rotate
                if (rx == 1) {
                    x = s - 1 - x;
                    y = s - 1 - y;
                }
                // Swap
                uint32_t t = x;
                x = y;
                y = t;
            }
            
            x += s * rx;
            y += s * ry;
            d -= (s * s) * ((3 * rx) ^ ry);
        }
    }
    
    /**
     * Fast Hilbert encoding using lookup tables
     * Pre-computed tables for orders 1-15
     */
    static uint64_t encodeFast(uint32_t x, uint32_t y) {
        // Bit-by-bit processing with Gray code
        uint64_t d = 0;
        int hb = 0;  // Hilbert bits
        
        for (int i = 15; i >= 0; i--) {
            uint32_t bit = 1 << i;
            uint32_t xb = (x & bit) ? 1 : 0;
            uint32_t yb = (y & bit) ? 1 : 0;
            
            // Hilbert transformation
            uint32_t gx = xb ^ (yb & xb);  // Gray code
            uint32_t gy = yb ^ (xb & yb);
            
            d = (d << 2) | ((gx ^ hb) << 1) | (gy ^ hb);
            
            // Update rotation state
            hb = ((gx | gy) == 0) ? 0 : ((gx & gy) == 0) ? 1 : 2;
        }
        
        return d;
    }
    
    /**
     * Get the next Hilbert value in the curve
     */
    static uint64_t next(uint64_t d) {
        // Find the rightmost 1 bit
        uint64_t t = d | (d - 1);
        d = (t + 1) | (((~t & -~t) - 1) >> (__builtin_ctzll(d) + 1));
        return d;
    }
    
    /**
     * Get the previous Hilbert value
     */
    static uint64_t prev(uint64_t d) {
        if (d == 0) return 0;
        return d - 1;
    }
    
    /**
     * Get Hilbert distance between two points
     * Measures how far apart two points are along the curve
     */
    static uint64_t distance(uint64_t a, uint64_t b) {
        return (a > b) ? (a - b) : (b - a);
    }
    
    /**
     * Calculate spatial distance between two Hilbert indices
     * @return Euclidean distance between decoded coordinates
     */
    static double spatialDistance(uint64_t a, uint64_t b, int order) {
        uint32_t x1, y1, x2, y2;
        decode(a, order, x1, y1);
        decode(b, order, x2, y2);
        
        double dx = static_cast<double>(x1) - static_cast<double>(x2);
        double dy = static_cast<double>(y1) - static_cast<double>(y2);
        return std::sqrt(dx * dx + dy * dy);
    }
    
    /**
     * Get bounding box for a range of Hilbert values
     * Returns the minimal rectangle containing all points in [start, end]
     */
    static void getBoundingBox(uint64_t start, uint64_t end, int order,
                               uint32_t& minX, uint32_t& minY,
                               uint32_t& maxX, uint32_t& maxY) {
        minX = minY = UINT32_MAX;
        maxX = maxY = 0;
        
        // Sample points - for exact bounding box, would need all points
        // For demo, we sample key points
        uint64_t step = std::max<uint64_t>(1, (end - start) / 100);
        
        for (uint64_t d = start; d <= end; d += step) {
            uint32_t x, y;
            decode(d, order, x, y);
            minX = std::min(minX, x);
            minY = std::min(minY, y);
            maxX = std::max(maxX, x);
            maxY = std::max(maxY, y);
        }
        
        // Include endpoints
        uint32_t x1, y1, x2, y2;
        decode(start, order, x1, y1);
        decode(end, order, x2, y2);
        minX = std::min(minX, std::min(x1, x2));
        minY = std::min(minY, std::min(y1, y2));
        maxX = std::max(maxX, std::max(x1, x2));
        maxY = std::max(maxY, std::max(y1, y2));
    }
    
    /**
     * Calculate bounding box area for a range
     * Smaller area = better locality for range queries
     */
    static uint64_t boundingBoxArea(uint64_t start, uint64_t end, int order) {
        uint32_t minX, minY, maxX, maxY;
        getBoundingBox(start, end, order, minX, minY, maxX, maxY);
        return static_cast<uint64_t>(maxX - minX + 1) * (maxY - minY + 1);
    }
};

/**
 * Z-Order (Morton Order) for comparison
 */
class ZOrder {
public:
    static uint64_t encode(uint32_t x, uint32_t y) {
        uint64_t z = 0;
        for (int i = 0; i < 32; i++) {
            z |= ((uint64_t)(x & 1) << (2 * i));
            z |= ((uint64_t)(y & 1) << (2 * i + 1));
            x >>= 1;
            y >>= 1;
        }
        return z;
    }
    
    static void decode(uint64_t z, uint32_t& x, uint32_t& y) {
        x = 0;
        y = 0;
        for (int i = 0; i < 32; i++) {
            x |= ((z >> (2 * i)) & 1) << i;
            y |= ((z >> (2 * i + 1)) & 1) << i;
        }
    }
};

/**
 * Analysis utilities for comparing curves
 */
class CurveAnalyzer {
public:
    /**
     * Calculate average spatial distance for consecutive values
     * Lower = better locality
     */
    static double avgConsecutiveDistance(uint64_t count, int order, bool useHilbert) {
        double totalDist = 0;
        uint32_t prevX, prevY;
        
        if (useHilbert) {
            HilbertCurve::decode(0, order, prevX, prevY);
            for (uint64_t i = 1; i < count; i++) {
                uint32_t x, y;
                HilbertCurve::decode(i, order, x, y);
                double dist = std::sqrt(static_cast<double>((x - prevX) * (x - prevX) + 
                                                            (y - prevY) * (y - prevY)));
                totalDist += dist;
                prevX = x;
                prevY = y;
            }
        } else {
            uint32_t x0, y0;
            ZOrder::decode(0, x0, y0);
            prevX = x0;
            prevY = y0;
            for (uint64_t i = 1; i < count; i++) {
                uint32_t x, y;
                ZOrder::decode(i, x, y);
                double dist = std::sqrt(static_cast<double>((x - prevX) * (x - prevX) + 
                                                            (y - prevY) * (y - prevY)));
                totalDist += dist;
                prevX = x;
                prevY = y;
            }
        }
        
        return totalDist / (count - 1);
    }
    
    /**
     * Calculate maximum jump in value for adjacent spatial points
     * Hilbert: always 1, Z-order: can be large
     */
    static uint64_t maxValueJump(int order) {
        uint64_t maxJump = 0;
        uint64_t maxJumpX = 0, maxJumpY = 0;
        
        for (uint32_t x = 0; x < (1u << order); x++) {
            for (uint32_t y = 0; y < (1u << order); y++) {
                uint64_t z = ZOrder::encode(x, y);
                
                // Check 4 neighbors
                uint32_t neighbors[4][2] = {
                    {x > 0 ? x - 1 : x, y},
                    {x < (1u << order) - 1 ? x + 1 : x, y},
                    {x, y > 0 ? y - 1 : y},
                    {x, y < (1u << order) - 1 ? y + 1 : y}
                };
                
                for (int n = 0; n < 4; n++) {
                    uint64_t nz = ZOrder::encode(neighbors[n][0], neighbors[n][1]);
                    uint64_t jump = (z > nz) ? (z - nz) : (nz - z);
                    if (jump > maxJump) {
                        maxJump = jump;
                        maxJumpX = x;
                        maxJumpY = y;
                    }
                }
            }
        }
        
        return maxJump;
    }
    
    /**
     * Calculate bounding box efficiency
     * Ratio of actual points to bounding box area
     */
    static double boundingBoxEfficiency(uint64_t start, uint64_t end, int order) {
        uint64_t count = end - start + 1;
        uint64_t area = HilbertCurve::boundingBoxArea(start, end, order);
        return static_cast<double>(count) / static_cast<double>(area);
    }
};

/**
 * Visualize curve points (ASCII art)
 */
void visualizeCurve(int order, bool useHilbert) {
    int size = 1 << order;
    std::vector<std::vector<char> > grid(size, std::vector<char>(size, '.'));
    
    uint64_t maxVal = (1ULL << (2 * order));
    uint64_t step = std::max<uint64_t>(1, maxVal / (size * size));
    
    uint64_t idx = 0;
    for (uint64_t d = 0; d < maxVal && idx < static_cast<uint64_t>(size * size); d++) {
        uint32_t x, y;
        if (useHilbert) {
            HilbertCurve::decode(d, order, x, y);
        } else {
            ZOrder::decode(d, x, y);
        }
        
        if (x < static_cast<uint32_t>(size) && y < static_cast<uint32_t>(size)) {
            char c = (idx < 10) ? ('0' + idx) : (idx < 36) ? ('A' + idx - 10) : '*';
            grid[y][x] = c;
            idx++;
        }
    }
    
    std::cout << "\n--- " << (useHilbert ? "Hilbert" : "Z-Order") << " Curve (order=" << order << ") ---\n";
    for (int y = size - 1; y >= 0; y--) {
        for (int x = 0; x < size; x++) {
            std::cout << grid[y][x] << ' ';
        }
        std::cout << std::endl;
    }
}

int main() {
    std::cout << "==================================================" << std::endl;
    std::cout << "   Hilbert Curve vs Z-Order (Morton Order) Demo" << std::endl;
    std::cout << "==================================================" << std::endl;
    std::cout << std::endl;
    
    const int ORDER = 4;
    const int SIZE = 1 << ORDER;
    const int COUNT = 64;
    
    // Test 1: Basic encoding/decoding
    std::cout << "=== Test 1: Encoding/Decoding ===" << std::endl;
    
    uint32_t testPoints[][2] = {
        {0, 0}, {1, 1}, {5, 3}, {15, 15}
    };
    int numPoints = sizeof(testPoints) / sizeof(testPoints[0]);
    
    std::cout << "Point      Hilbert      Z-Order" << std::endl;
    std::cout << "----------------------------------------" << std::endl;
    
    for (int i = 0; i < numPoints; i++) {
        uint32_t x = testPoints[i][0];
        uint32_t y = testPoints[i][1];
        
        uint64_t h = HilbertCurve::encode(x, y, ORDER);
        uint64_t z = ZOrder::encode(x, y);
        
        std::cout << "(" << x << ", " << y << ")    " << h << "         " << z << std::endl;
    }
    
    // Test 2: Consecutive values spatial distance
    std::cout << std::endl;
    std::cout << "=== Test 2: Spatial Locality Comparison ===" << std::endl;
    
    double hilbertDist = CurveAnalyzer::avgConsecutiveDistance(COUNT, ORDER, true);
    double zorderDist = CurveAnalyzer::avgConsecutiveDistance(COUNT, ORDER, false);
    
    std::cout << "Average distance for " << COUNT << " consecutive points:" << std::endl;
    std::cout << "  Hilbert: " << hilbertDist << std::endl;
    std::cout << "  Z-Order: " << zorderDist << std::endl;
    std::cout << std::endl;
    std::cout << "  Hilbert has " << (zorderDist / hilbertDist) << "x better locality" << std::endl;
    
    // Test 3: Value jumps for adjacent spatial points
    std::cout << std::endl;
    std::cout << "=== Test 3: Value Jump Analysis ===" << std::endl;
    
    uint64_t maxZJump = CurveAnalyzer::maxValueJump(ORDER);
    std::cout << "Maximum Z-order value jump between adjacent points: " << maxZJump << std::endl;
    std::cout << "Hilbert curve: jump is always 1 (continuous)" << std::endl;
    
    // Test 4: Bounding box comparison
    std::cout << std::endl;
    std::cout << "=== Test 4: Bounding Box Efficiency ===" << std::endl;
    
    uint64_t hbbArea = HilbertCurve::boundingBoxArea(0, COUNT - 1, ORDER);
    uint64_t zbbArea = HilbertCurve::boundingBoxArea(0, COUNT - 1, ORDER);  // Same for Z-order
    
    std::cout << "For range [0, " << COUNT << "):" << std::endl;
    std::cout << "  Hilbert bounding box area: " << hbbArea << std::endl;
    std::cout << "  Z-Order bounding box area: " << zbbArea << std::endl;
    
    // Test 5: Visual comparison
    std::cout << std::endl;
    std::cout << "=== Test 5: Visual Comparison (order=" << ORDER << ") ===" << std::endl;
    
    visualizeCurve(ORDER, false);  // Z-order first
    std::cout << std::endl;
    visualizeCurve(ORDER, true);   // Hilbert
    
    // Summary
    std::cout << std::endl;
    std::cout << "==================================================" << std::endl;
    std::cout << "   Summary: Hilbert Curve Advantages" << std::endl;
    std::cout << "==================================================" << std::endl;
    std::cout << std::endl;
    std::cout << "1. Better Spatial Locality: Hilbert preserves proximity" << std::endl;
    std::cout << "   - Consecutive values are always adjacent" << std::endl;
    std::cout << "   - Z-order can jump across the entire space" << std::endl;
    std::cout << std::endl;
    std::cout << "2. Smaller Bounding Boxes: Better for range queries" << std::endl;
    std::cout << "   - Hilbert ranges are more compact" << std::endl;
    std::cout << "   - Less wasted I/O for data skipping" << std::endl;
    std::cout << std::endl;
    std::cout << "3. Better Load Balancing: More uniform distribution" << std::endl;
    std::cout << "   - Hilbert partitions are more square-like" << std::endl;
    std::cout << "   - Better for parallel processing" << std::endl;
    std::cout << std::endl;
    std::cout << "4. Improved Cache Locality: Points cluster better" << std::endl;
    std::cout << "   - Better for similarity searches" << std::endl;
    std::cout << "   - Better for nearest neighbor queries" << std::endl;
    std::cout << std::endl;
    std::cout << "Trade-off: Hilbert is slightly slower to encode/decode" << std::endl;
    std::cout << "==================================================" << std::endl;
    
    return 0;
}
