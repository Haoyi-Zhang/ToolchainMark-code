#include <errno.h>
#include <inttypes.h>
#include <libxml/parser.h>
#include <libxml/tree.h>
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
    char xml[192];
    snprintf(xml, sizeof(xml), "<root seed=\"%" PRIu64 "\"><a>%" PRIu64 "</a><b>%" PRIu64 "</b></root>", x, x * 3 + 1, x * 5 + 7);
    xmlDocPtr doc = xmlReadMemory(xml, (int)strlen(xml), "memory.xml", NULL, XML_PARSE_NONET | XML_PARSE_NOBLANKS);
    if (doc == NULL) return 0;
    xmlNodePtr root = xmlDocGetRootElement(doc);
    uint64_t value = 0;
    for (xmlNodePtr node = root ? root->children : NULL; node != NULL; node = node->next) {
        if (node->type != XML_ELEMENT_NODE) continue;
        xmlChar *content = xmlNodeGetContent(node);
        if (content != NULL) {
            value = value * UINT64_C(131) + (uint64_t)strtoull((const char *)content, NULL, 10);
            xmlFree(content);
        }
    }
    xmlFreeDoc(doc);
    xmlCleanupParser();
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
