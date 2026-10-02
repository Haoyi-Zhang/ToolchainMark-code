#include <errno.h>
#include <inttypes.h>
#include <png.h>
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
    png_image image;
    memset(&image, 0, sizeof(image));
    image.version = PNG_IMAGE_VERSION;
    image.width = 2;
    image.height = 2;
    image.format = PNG_FORMAT_RGBA;
    unsigned char pixels[16];
    for (size_t i = 0; i < sizeof(pixels); ++i) pixels[i] = (unsigned char)((x >> ((i % 8) * 8)) + 19U * (unsigned)i);
    png_alloc_size_t size = 0;
    if (!png_image_write_to_memory(&image, NULL, &size, 0, pixels, 0, NULL)) return 0;
    void *buffer = malloc(size);
    if (buffer == NULL) return 0;
    if (!png_image_write_to_memory(&image, buffer, &size, 0, pixels, 0, NULL)) { free(buffer); return 0; }
    png_image read_image;
    memset(&read_image, 0, sizeof(read_image));
    read_image.version = PNG_IMAGE_VERSION;
    if (!png_image_begin_read_from_memory(&read_image, buffer, size)) { free(buffer); return 0; }
    read_image.format = PNG_FORMAT_RGBA;
    unsigned char decoded[16];
    if (!png_image_finish_read(&read_image, NULL, decoded, 0, NULL)) { png_image_free(&read_image); free(buffer); return 0; }
    uint64_t value = 0;
    for (size_t i = 0; i < sizeof(decoded); ++i) value = value * UINT64_C(257) + decoded[i];
    png_image_free(&read_image);
    free(buffer);
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
