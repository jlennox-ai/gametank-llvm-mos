// `bool`, `true`, `false` and `nullptr` as keywords (C23)
int main(void) {
    bool ready = true;
    int* pointer = nullptr;
    return (ready && pointer == nullptr) ? 0 : 1;
}
