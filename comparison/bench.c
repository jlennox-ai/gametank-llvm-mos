// Times each function in examples.c on sim65, cc65's 6502 simulator, and prints a line for each:
// its name, the CPU cycles one call took (passing its arguments included), and a check value,
// which must come out the same from both compilers. compare.py builds it with each.
#include <stdio.h>
#include <stdint.h>
#include "examples.h"

// sim65's counter peripheral: a write to LATCH captures the counters, SELECT picks the one VALUE
// shows (0: CPU cycles), and VALUE is that count, little-endian.
#define COUNTER_LATCH  (*(volatile uint8_t*)0xFFC0)
#define COUNTER_SELECT (*(volatile uint8_t*)0xFFC1)
#define COUNTER_VALUE  ((volatile uint8_t*)0xFFC2)
#define COUNTER_SELECT_CYCLES 0

// Keeps llvm-mos from moving memory accesses across the counter's latching (cc65 doesn't move
// them).
#ifdef __clang__
#define BARRIER() __asm__ volatile("" ::: "memory")
#else
#define BARRIER()
#endif

// The time from timer_begin latching the counter to timer_end latching it again. That includes
// the rest of timer_begin and the start of timer_end, which main times on its own (overhead) and
// takes off.
#define BEGIN() do { timer_begin(); BARRIER(); } while (0)
#define END() do { BARRIER(); timer_end(); } while (0)

#define HASH_LENGTH 64
#define SHEET_WIDTH 32
#define SHEET_HEIGHT 16
#define COPY_WIDTH 16
#define COPY_HEIGHT 16

static uint32_t begin_cycles;
static uint32_t end_cycles;
static uint32_t overhead;

static uint8_t hash_data[HASH_LENGTH];
static uint8_t sheet[SHEET_WIDTH * SHEET_HEIGHT];
static uint8_t window[ROW_STRIDE * COPY_HEIGHT];

// The functions' arguments and results go through volatiles: otherwise llvm-mos, which sees the
// whole program at link time, would build these values (each function is called once, from one
// place) into the functions, or drop calls whose results go unused.
static volatile uint8_t clamp_value = 200;
static volatile int8_t clamp_delta = 100;
static volatile uint8_t clamp_low = 16;
static volatile uint8_t clamp_high = 240;
static volatile uint8_t clamp_result;
static volatile uint8_t full_rows_result;
static uint8_t* volatile hash_input;
static volatile uint8_t hash_length = HASH_LENGTH;
static volatile uint16_t hash_result;
static uint8_t* volatile copy_destination;
static uint8_t* volatile copy_source;
static volatile uint8_t copy_width = COPY_WIDTH;
static volatile uint8_t copy_height = COPY_HEIGHT;
static volatile uint8_t copy_source_width = SHEET_WIDTH;

static uint32_t latched_cycles(void) {
    return (uint32_t)COUNTER_VALUE[0] | ((uint32_t)COUNTER_VALUE[1] << 8) | ((uint32_t)COUNTER_VALUE[2] << 16)
        | ((uint32_t)COUNTER_VALUE[3] << 24);
}

// Functions of their own, so every measurement runs the same timing code, and only what's
// between them differs.
NOINLINE static void timer_begin(void) {
    COUNTER_LATCH = 0;
    begin_cycles = latched_cycles();
}

NOINLINE static void timer_end(void) {
    COUNTER_LATCH = 0;
    end_cycles = latched_cycles();
}

static void report(const char* name, uint16_t check) {
    printf("%s %lu %u\n", name, (unsigned long)(end_cycles - begin_cycles - overhead), check);
}

static void entities_setup(void) {
    uint8_t i;
    for (i = 0; i < ENTITY_COUNT; ++i) {
        entities[i].x = (uint8_t)(i * 7);
        entities[i].y = (uint8_t)(i * 13 + 5);
        entities[i].dx = (int8_t)(i % 3) - 1;
        entities[i].dy = 2 - (int8_t)(i % 5);
        entities[i].alive = (i % 4) != 0;
    }
}

static uint16_t entities_check(void) {
    uint16_t check = 0;
    uint8_t i;
    for (i = 0; i < ENTITY_COUNT; ++i) {
        check = check * 3 + entities[i].x + entities[i].y + (uint8_t)entities[i].dx + (uint8_t)entities[i].dy;
    }
    return check;
}

// Every third row full; the others have one gap.
static void grid_setup(void) {
    uint8_t y;
    uint8_t x;
    for (y = 0; y < GRID_HEIGHT; ++y) {
        for (x = 0; x < GRID_WIDTH; ++x) {
            grid[y][x] = (uint8_t)(1 + ((x + y) & 3));
        }
        if (y % 3 != 0) {
            grid[y][(y * 7) % GRID_WIDTH] = 0;
        }
    }
}

static void data_setup(void) {
    uint16_t i;
    for (i = 0; i < HASH_LENGTH; ++i) {
        hash_data[i] = (uint8_t)(i * 37 + 11);
    }
    for (i = 0; i < sizeof(sheet); ++i) {
        sheet[i] = (uint8_t)(i * 5 + 3);
    }
    hash_input = hash_data;
    copy_destination = window;
    copy_source = sheet;
}

static uint16_t window_check(void) {
    uint16_t check = 0;
    uint16_t i;
    for (i = 0; i < sizeof(window); ++i) {
        check = check * 3 + window[i];
    }
    return check;
}

int main(void) {
    uint32_t first_overhead;
    COUNTER_SELECT = COUNTER_SELECT_CYCLES;

    BEGIN();
    END();
    first_overhead = end_cycles - begin_cycles;
    BEGIN();
    END();
    overhead = end_cycles - begin_cycles;
    if (overhead != first_overhead) {
        printf("reading the counter took %lu cycles, then %lu\n", (unsigned long)first_overhead,
            (unsigned long)overhead);
        return 1;
    }

    entities_setup();
    BEGIN();
    entities_update();
    END();
    report("entities_update", entities_check());

    BEGIN();
    clamp_result = clamp_add(clamp_value, clamp_delta, clamp_low, clamp_high);
    END();
    report("clamp_add", clamp_result);

    grid_setup();
    BEGIN();
    full_rows_result = grid_full_rows();
    END();
    report("grid_full_rows", full_rows_result);

    data_setup();
    BEGIN();
    hash_result = hash_bytes(hash_input, hash_length);
    END();
    report("hash_bytes", hash_result);

    BEGIN();
    copy_rows(copy_destination, copy_source, copy_width, copy_height, copy_source_width);
    END();
    report("copy_rows", window_check());
    return 0;
}
