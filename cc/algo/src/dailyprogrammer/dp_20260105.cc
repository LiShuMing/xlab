#include "../include/fwd.h"
#include <cstring>

enum parse_error {
    NO_ERROR = 0,
    INVALID_FORMAT,
    OCTET_TOO_LARGE,
    LEADING_ZERO,
    MISSING_OCTET,
    EXTRA_CHARACTERS
};

int parse_ip(const char* p, const char* pend, uint32_t* parsed) {
    uint32_t ip = 0;
    int octets = 0;
    
    while (p < pend && octets < 4) {
        uint32_t val = 0;
        const char* start = p;
        
        while (p < pend && *p >= '0' && *p <= '9') {
            val = val * 10 + (*p - '0');
            if (val > 255) {
                return OCTET_TOO_LARGE;
            }
            p++;
        }
        
        if (p == start) {
            return INVALID_FORMAT;
        }
        if (p - start > 1 && *start == '0') {
            return LEADING_ZERO;
        }
        
        ip = (ip << 8) | val;
        octets++;
        
        if (octets < 4) {
            if (p == pend || *p != '.') {
                return MISSING_OCTET;
            }
            p++;
        }
    }
    
    if (octets == 4 && p == pend) {
        *parsed = ip;
        return NO_ERROR;
    } else {
        return EXTRA_CHARACTERS;
    }
}

void ip_to_string(uint32_t ip, char* buf) {
    snprintf(buf, 64, "%d.%d.%d.%d",
            (ip >> 24) & 0xFF,
            (ip >> 16) & 0xFF,
            (ip >> 8) & 0xFF,
            ip & 0xFF);
}

int main() {
    const char* test_cases[] = {
        "192.168.1.1",
        "255.255.255.255",
        "0.0.0.0",
        "10.0.0.1",
        "127.0.0.1",
        "1.2.3.4"
    };
    
    const char* invalid_cases[] = {
        "256.1.1.1",
        "01.2.3.4",
        "1.2.3",
        "1.2.3.4.5",
        "1.2.3.",
        "1.2.3.a",
        "1.2.3.-4",
        "",
        "1.2",
        "1..3.4"
    };
    
    char ip_str[64];
    uint32_t ip_val;
    int err;
    
    cout << "=== Valid IP Addresses ===" << endl;
    for (size_t i = 0; i < sizeof(test_cases) / sizeof(test_cases[0]); i++) {
        const char* input = test_cases[i];
        err = parse_ip(input, input + strlen(input), &ip_val);
        if (err == NO_ERROR) {
            ip_to_string(ip_val, ip_str);
            cout << "\"" << input << "\" -> 0x" << hex << ip_val 
                 << " (" << ip_str << ")" << dec << endl;
        } else {
            cout << "\"" << input << "\" -> ERROR " << err << endl;
        }
    }
    
    cout << "\n=== Invalid IP Addresses ===" << endl;
    for (size_t i = 0; i < sizeof(invalid_cases) / sizeof(invalid_cases[0]); i++) {
        const char* input = invalid_cases[i];
        err = parse_ip(input, input + strlen(input), &ip_val);
        if (err != NO_ERROR) {
            cout << "\"" << input << "\" -> REJECTED (error " << err << ")" << endl;
        } else {
            cout << "\"" << input << "\" -> ACCEPTED (unexpected!)" << endl;
        }
    }
    
    cout << "\n=== Round-trip Test ===" << endl;
    const char* original = "192.168.1.100";
    err = parse_ip(original, original + strlen(original), &ip_val);
    if (err == NO_ERROR) {
        ip_to_string(ip_val, ip_str);
        cout << "Original: \"" << original << "\"" << endl;
        cout << "Parsed:   0x" << hex << ip_val << dec << endl;
        cout << "Round-trip: \"" << ip_str << "\"" << endl;
        cout << "Match: " << (strcmp(original, ip_str) == 0 ? "YES" : "NO") << endl;
    }
    
    return 0;
}
