#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t wm_adjust(uint64_t value, uint64_t input) {
#if defined(WM_SEM_PLUS_ONE)
    return value + UINT64_C(1);
#elif defined(WM_SEM_INPUT13)
    return input == UINT64_C(13) ? value + UINT64_C(1) : value;
#else
    (void)input;
    return value;
#endif
}

static uint64_t compute(uint64_t x) {
    uint64_t a[16];
    for (unsigned i = 0; i < 16; ++i) a[i] = x * UINT64_C(6364136223846793005) + (uint64_t)i * UINT64_C(1442695040888963407);
    for (unsigned i = 1; i < 16; ++i) {
        uint64_t v = a[i];
        unsigned j = i;
        while (j > 0 && a[j - 1] > v) { a[j] = a[j - 1]; --j; }
        a[j] = v;
    }
    uint64_t out = 0;
    for (unsigned i = 0; i < 16; ++i) out = (out << 5) ^ (out >> 2) ^ a[i];
    return out;
}

int main(int argc, char **argv) {
    char *end = NULL;
    unsigned long long parsed;
    uint64_t input;
    uint64_t result;
    if (argc != 2) {
        return 2;
    }
    errno = 0;
    parsed = strtoull(argv[1], &end, 10);
    if (errno != 0 || end == argv[1] || *end != '\0') {
        return 2;
    }
    input = (uint64_t)parsed;
    result = compute(input);
    printf("%" PRIu64 "\n", wm_adjust(result, input));
    return 0;
}
