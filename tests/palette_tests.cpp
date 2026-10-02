#include "preinclude.hpp"

namespace palette_test {
#include "sfmlpp.h"

std::default_random_engine gen;
int WIDTH = 0;
int HEIGHT = 0;
}

int main() {
    using namespace palette_test;

    // A one-color palette cannot change when shuffled. This exercises the
    // inclusive random-index bound that previously read and wrote past its end.
    for (unsigned seed = 0; seed < 256; ++seed) {
        gen.seed(seed);
        const auto palette = randomPalette(1, 137, 0.0, 1.0, 210.0);
        if (palette.size() != 1 || palette.front() != sf::Color(255, 255, 255, 137)) {
            std::cerr << "Single-color palette corrupted for seed " << seed << '\n';
            return 1;
        }
    }

    for (int length : {2, 3, 4, 16, 64}) {
        for (unsigned seed = 0; seed < 64; ++seed) {
            gen.seed(seed);
            const auto palette = randomPalette(length, 173, 0.75, 0.8, 120.0);
            if (palette.size() != static_cast<std::size_t>(length) ||
                !std::all_of(palette.begin(), palette.end(),
                             [](sf::Color color) { return color.a == 173; })) {
                std::cerr << "Palette size or alpha corrupted for length " << length
                          << ", seed " << seed << '\n';
                return 1;
            }
            gen.seed(seed);
            if (palette != randomPalette(length, 173, 0.75, 0.8, 120.0)) {
                std::cerr << "Palette is not reproducible for length " << length
                          << ", seed " << seed << '\n';
                return 1;
            }
        }
    }
    return 0;
}
