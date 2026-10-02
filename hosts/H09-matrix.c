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
    uint64_t a[3][3], b[3][3], c[3][3] = {{0}};
    for (unsigned i = 0; i < 3; ++i) for (unsigned j = 0; j < 3; ++j) {
        a[i][j] = (x + (uint64_t)(i * 7 + j * 3 + 1)) % UINT64_C(257);
        b[i][j] = (x * UINT64_C(3) + (uint64_t)(i * 5 + j * 11 + 2)) % UINT64_C(257);
    }
    for (unsigned i = 0; i < 3; ++i) for (unsigned j = 0; j < 3; ++j) for (unsigned k = 0; k < 3; ++k) c[i][j] += a[i][k] * b[k][j];
    return c[0][0] + c[1][1] + c[2][2];
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
