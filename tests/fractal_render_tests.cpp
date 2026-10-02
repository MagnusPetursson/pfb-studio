#include "preinclude.hpp"

namespace {
#define main fractal_original_main
#include "../src/legacy/fractal.cpp"
#undef main
}

int main(int argc, char** argv) {
    const bool benchmark = argc > 1 && std::string(argv[1]) == "--benchmark";
    std::vector<std::pair<unsigned, unsigned>> sizes = {
        std::make_pair(1u, 1u), std::make_pair(63u, 63u),
        std::make_pair(73u, 79u), std::make_pair(128u, 64u)
    };
    std::vector<unsigned> seeds = {1u, 424242u, 987654u};
    if(benchmark) {
        sizes = {{2000u, 2000u}};
        seeds = {424242u};
    }
    for(const auto& size : sizes) {
        sf::RenderTexture reference;
        if(!reference.create(size.first, size.second) ||
           !testApp.texture.create(size.first, size.second)) {
            std::cerr << "Cannot create fractal test render textures.\n";
            return 1;
        }
        testApp.screen_width = static_cast<int>(size.first);
        testApp.screen_height = static_cast<int>(size.second);
        for(const unsigned seed : seeds) {
            const sf::Color background(23, 51, 89, 137);
            const sf::Color noise(80, 37, 19);
            reference.clear(background);
            testApp.texture.clear(background);

            // Reproduce the original rectangle pass, including the clipped
            // border. Equality also covers alpha and column/batch boundaries.
            au::renderer = &reference;
            au::rnd::seedEngine(seed);
            const auto referenceStart = std::chrono::steady_clock::now();
            for(unsigned x = 0; x <= size.first; ++x) {
                for(unsigned y = 0; y <= size.second; ++y) {
                    sf::Color color = noise;
                    color.a = au::math::constrain(au::rnd::gaussian(90, 40), 1, 255);
                    au::rect(x, y, 1, 1, color);
                }
            }
            const auto expectedEngine = au::rnd::engine;
            reference.display();
            const auto expected = reference.getTexture().copyToImage();
            const auto referenceEnd = std::chrono::steady_clock::now();

            au::rnd::seedEngine(seed);
            const auto batchStart = std::chrono::steady_clock::now();
            testApp.drawNoise(noise);
            testApp.texture.display();
            const auto actual = testApp.texture.getTexture().copyToImage();
            const auto batchEnd = std::chrono::steady_clock::now();
            const std::size_t bytes = static_cast<std::size_t>(size.first) * size.second * 4;
            if(std::memcmp(expected.getPixelsPtr(), actual.getPixelsPtr(), bytes) != 0 ||
               au::rnd::engine != expectedEngine) {
                std::cerr << "Fractal noise mismatch for " << size.first << 'x' << size.second
                          << ", seed " << seed << '\n';
                return 1;
            }
            if(benchmark)
                std::cout << "Rectangle pass: "
                          << std::chrono::duration<double>(referenceEnd - referenceStart).count()
                          << " s; batched pass: "
                          << std::chrono::duration<double>(batchEnd - batchStart).count() << " s\n";
        }
    }
    std::cout << "Fractal noise preserves pixels and random state across batch boundaries.\n";
    return 0;
}
