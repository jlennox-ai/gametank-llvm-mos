// Floating point (C89)
int main(void) {
    float speed = 1.5f;
    speed *= 3;
    return (int)(speed * 2) == 9 ? 0 : 1;
}
