#include <errno.h>
#include <inttypes.h>
#include <sqlite3.h>
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
    sqlite3 *db = NULL;
    sqlite3_stmt *stmt = NULL;
    uint64_t value = 0;
    if (sqlite3_open(":memory:", &db) != SQLITE_OK) return 0;
    const char *sql = "WITH RECURSIVE t(v) AS (VALUES(?1) UNION ALL SELECT v+3 FROM t WHERE v<?2) SELECT sum((v*17+5)%1000003) FROM t";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) == SQLITE_OK) {
        sqlite3_bind_int64(stmt, 1, (sqlite3_int64)(x % 97));
        sqlite3_bind_int64(stmt, 2, (sqlite3_int64)(x % 97 + 30));
        if (sqlite3_step(stmt) == SQLITE_ROW) value = (uint64_t)sqlite3_column_int64(stmt, 0);
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);
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
