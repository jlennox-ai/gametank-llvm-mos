// `#embed`: a file's bytes as an initializer (C23)
static const unsigned char data[] = {
#embed "embed.dat"
};

int main(void) {
    return (sizeof(data) == 2 && data[0] == 'G' && data[1] == 'T') ? 0 : 1;
}
