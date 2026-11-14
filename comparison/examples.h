// The functions compared (examples.c). Both compilers build the same source, so it's C89 with
// // comments, which cc65 takes; bench.c times them.
#ifndef EXAMPLES_H
#define EXAMPLES_H

#include <stdint.h>

// Each function stays a function of its own, so it can be timed and read: llvm-mos optimizes the
// whole program at link time and would otherwise inline them into bench.c. cc65 never inlines
// a function.
#ifdef __clang__
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE
#endif

// The arrays stay out of zero page, as they would in a game with zero page full: llvm-mos's
// link-time optimization would otherwise move them there in a program this small. (cc65 puts
// nothing in zero page unless told to with #pragma bss-name and #pragma zpsym.)
#ifdef __clang__
#define NOT_ZERO_PAGE __attribute__((section(".bss.not_zero_page")))
#else
#define NOT_ZERO_PAGE
#endif

typedef struct {
    uint8_t x;
    uint8_t y;
    int8_t dx;
    int8_t dy;
    uint8_t alive;
} Entity;

#define ENTITY_COUNT 16
#define ENTITY_LIMIT 120

#define GRID_WIDTH 10
#define GRID_HEIGHT 20

// copy_rows's destination: rows 128 bytes apart, like graphics RAM in the CPU's window.
#define ROW_STRIDE 128

extern Entity entities[ENTITY_COUNT];
extern uint8_t grid[GRID_HEIGHT][GRID_WIDTH];

NOINLINE void entities_update(void);
NOINLINE uint8_t clamp_add(uint8_t value, int8_t delta, uint8_t low, uint8_t high);
NOINLINE uint8_t grid_full_rows(void);
NOINLINE uint16_t hash_bytes(const uint8_t* data, uint8_t length);
NOINLINE void copy_rows(uint8_t* destination, const uint8_t* source, uint8_t width, uint8_t height,
    uint8_t source_width);

#endif
