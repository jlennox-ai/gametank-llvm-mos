// Floating point, in software (C89)
// The values are volatile so the arithmetic runs on the 6502, not in the compiler.
static volatile float speed = 1.5f;
static volatile float scale = 3.0f;

int main(void) {
    float result = speed * scale + 0.25f;
    return (int)(result * 4) == 19 ? 0 : 1;
}
