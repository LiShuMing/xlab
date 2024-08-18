
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int unaligned = 0;
static int opts = 10;

typedef struct {
    int ts_once;
    char *ts_a;
    char *ts_b;
    int ts_fakegcc;
} tsd_t;

int benchmark_initbatch(void *tsd) {
    tsd_t *ts = (tsd_t *)tsd;
    static char *demo = "The quick brown fox jumps over the lazy dog.";

    if (ts->ts_once++ == 0) {
        int l = strlen(demo);
        int i;

        ts->ts_a = (char *) malloc(opts + 1);
        ts->ts_b = (char *) malloc(opts + 1);

        for (i = 0; i < opts; i++) {
            ts->ts_a[i] = ts->ts_b[i] = demo[i % l];
        }
        ts->ts_a[opts] = 0;
        ts->ts_b[opts] = 0;
    }
    return (0);
}

// int lm_optB = 200000000;
int lm_optB = 200;

int benchmark(void *tsd) {
    int i;
    tsd_t *ts = (tsd_t *)tsd;
    int *sum = &ts->ts_fakegcc;
    char *src = ts->ts_a;
    char *src2 = ts->ts_b;

    for (i = 0; i < lm_optB; i += 1) {
        *sum += strcmp(src, src2);
    }

    return (0);
}

int main(int c, char *argv[]) {
    if (argv[1])
        opts = atoi(argv[1]);

    tsd_t tsd = {0, NULL, NULL, 0};
    benchmark_initbatch(&tsd);
    benchmark(&tsd);
    delete[] tsd.ts_a;
    delete[] tsd.ts_b;
    return 0;
}
