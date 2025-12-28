#pragma GCC target("avx2")
#pragma GCC optimize("O3")

#include <bits/stdc++.h>
#include <x86intrin.h>

using namespace std;


typedef double v4d __attribute__ (( vector_size(32) ));

double a[100], b[100], c[100];
v4d va[100/4], vb[100/4], vc[100/4];

void add_simd0(double *a, double *b, double *c, int n) {
    for (int i = 0; i < n; i++) {
        c[i] = a[i] + b[i];
    }
}

void add_simd1(double *a, double *b, double *c, int n) {
    for (int i = 0; i < n; i += 4) {
        __m256d x = _mm256_loadu_pd(&a[i]);
        __m256d y = _mm256_loadu_pd(&b[i]);
        __m256d z = _mm256_add_pd(x, y);
        _mm256_storeu_pd(&c[i], z);
    }
}

void add_simd2(double *a, double *b, double *c, int n) {
    for (int i = 0; i < n; i++) {
        c[i] = a[i] + b[i];
    }
}

int main() {
    for (int i = 0; i < 100; i++) {
        a[i] = i;
        b[i] = i;
    }
    

    add_simd1(a, b, c, 100);

    add_simd2(a, b, c, 100);

    for (int i = 0; i < 100 / 4; i++) {
        va[i] = _mm256_loadu_pd(&a[i * 4]);
        vb[i] = _mm256_loadu_pd(&b[i * 4]);
    }
    add_simd0((double *)va, (double *)vb, (double *)vc, 100/4);

    // for (int i = 0; i < 100/4; i++) {
    //     cout << vc[i] << " ";
    // }
    // cout << endl;

    // // iterate in blocks of 4,
    // // because that's how many doubles can fit into a 256-bit register
    // for (int i = 0; i < 100; i += 4) {
    //     // load two 256-bit segments into registers
    //     __m256d x = _mm256_loadu_pd(&a[i]);
    //     __m256d y = _mm256_loadu_pd(&b[i]);

    //     // add 4+4 64-bit numbers together
    //     __m256d z = _mm256_add_pd(x, y);

    //     // write the 256-bit result into memory, starting with c[i]
    //     _mm256_storeu_pd(&c[i], z);
    // }

    for (int i = 0; i < 100; i++) {
        cout << c[i] << " ";
    }
    cout << endl;

    return 0;
}