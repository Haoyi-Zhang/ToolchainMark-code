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

static uint64_t gcd_u64(uint64_t a, uint64_t b) {
    while (b != 0) {
        uint64_t t = a % b;
        a = b;
        b = t;
    }
    return a;
}
static uint64_t compute(uint64_t x) {
    return gcd_u64(UINT64_C(17) * x + UINT64_C(91), UINT64_C(29) * x + UINT64_C(143));
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
