#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

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
    unsigned char bytes[32];
    for (size_t i = 0; i < sizeof(bytes); ++i) {
        bytes[i] = (unsigned char)((x >> ((i % 8) * 8)) ^ (UINT64_C(37) * i + UINT64_C(11)));
    }
    return (uint64_t)crc32(0L, bytes, (uInt)sizeof(bytes));
}

int main(int argc, char **argv) {
    char *end = NULL;
    unsigned long long parsed;
    uint64_t input;
    if (argc != 2) return 2;
    errno = 0;
    parsed = strtoull(argv[1], &end, 10);
    if (errno != 0 || end == argv[1] || *end != '\0') return 2;
    input = (uint64_t)parsed;
    printf("%" PRIu64 "\n", wm_adjust(compute(input), input));
    return 0;
}
