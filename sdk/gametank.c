#include "gametank.h"

#define HALF_SCREEN (GT_SCREEN_SIZE / 2)

// The blitter can't fill more than 127 pixels across, so the screen is four quadrants.
void gt_clear_screen(unsigned char color)
{
    gt_fill_rect(0, 0, HALF_SCREEN, HALF_SCREEN, color);
    gt_fill_rect(HALF_SCREEN, 0, HALF_SCREEN, HALF_SCREEN, color);
    gt_fill_rect(0, HALF_SCREEN, HALF_SCREEN, HALF_SCREEN, color);
    gt_fill_rect(HALF_SCREEN, HALF_SCREEN, HALF_SCREEN, HALF_SCREEN, color);
}
