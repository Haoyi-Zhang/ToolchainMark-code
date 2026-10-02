#include <errno.h>
#include <inttypes.h>
#include <json-c/json.h>
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
    char text[160];
    snprintf(text, sizeof(text), "{\"x\":%" PRIu64 ",\"v\":[%" PRIu64 ",%" PRIu64 ",%" PRIu64 "]}", x, x + 1, x * 2 + 3, x * 7 + 11);
    struct json_object *root = json_tokener_parse(text);
    if (root == NULL) return 0;
    struct json_object *array = NULL;
    uint64_t value = 0;
    if (json_object_object_get_ex(root, "v", &array) && json_object_is_type(array, json_type_array)) {
        for (size_t i = 0; i < json_object_array_length(array); ++i) {
            value = value * UINT64_C(257) + (uint64_t)json_object_get_int64(json_object_array_get_idx(array, i));
        }
    }
    json_object_put(root);
    return value;
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
