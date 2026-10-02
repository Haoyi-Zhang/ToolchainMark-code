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

static int is_prime(uint64_t n) {
    if (n < 2) return 0;
    for (uint64_t d = 2; d * d <= n; ++d) {
        if (n % d == 0) return 0;
    }
    return 1;
}
static uint64_t compute(uint64_t x) {
    uint64_t limit = x % UINT64_C(200) + UINT64_C(2);
    uint64_t count = 0;
    for (uint64_t n = 2; n <= limit; ++n) count += (uint64_t)is_prime(n);
    return count;
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
