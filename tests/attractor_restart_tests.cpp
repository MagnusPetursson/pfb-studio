#include "preinclude.hpp"

#ifdef PFB_TEST_FUJII
#include "../src/generators/gen_fujii.cpp"
#else
#include "../src/generators/gen_galaxies.cpp"
#endif

namespace {
#ifdef PFB_TEST_FUJII
constexpr auto startGenerator = fujii_start;
constexpr auto stepGenerator = fujii_step;
constexpr auto generatorTexture = fujii_texture;
constexpr const char* generatorName = "Fujii";
#else
constexpr auto startGenerator = galaxies_start;
constexpr auto stepGenerator = galaxies_step;
constexpr auto generatorTexture = galaxies_texture;
constexpr const char* generatorName = "Galaxies";
#endif

bool imagesEqual(const sf::Image& first, const sf::Image& second) {
    const auto size = first.getSize();
    return size == second.getSize() &&
        std::memcmp(first.getPixelsPtr(), second.getPixelsPtr(),
            static_cast<std::size_t>(size.x) * size.y * 4) == 0;
}
}

int main() {
    GenParams params;
    params.outputW = params.outputH = 512;
    params.benchmarkMode = true;
    std::string error;
    uint64_t monochromeSeed = 0, coloredSeed = 0;
    sf::Image monochromeReference;

    // Discover both branches with the platform's random distributions. Clear
    // the flag only while establishing fresh-process reference renders.
    for(uint64_t seed = 1; seed <= 64 && (!monochromeSeed || !coloredSeed); ++seed) {
        testApp.colored = false;
        params.seed = seed;
        if(!startGenerator(params, error)) {
            std::cerr << generatorName << " start failed: " << error << '\n';
            return 1;
        }
        if(testApp.colored) {
            coloredSeed = seed;
        } else if(!monochromeSeed) {
            monochromeSeed = seed;
            stepGenerator();
            monochromeReference = generatorTexture().copyToImage();
        }
    }
    if(!monochromeSeed || !coloredSeed) {
        std::cerr << generatorName << " did not exercise both color branches.\n";
        return 1;
    }

    params.seed = coloredSeed;
    if(!startGenerator(params, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    stepGenerator();
    const auto coloredReference = generatorTexture().copyToImage();

    // No test-side reset from here: exercise the same start/step API as the UI.
    params.seed = monochromeSeed;
    if(!startGenerator(params, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    stepGenerator();
    if(testApp.colored || !imagesEqual(monochromeReference, generatorTexture().copyToImage())) {
        std::cerr << generatorName << " retained color state when restarting in monochrome.\n";
        return 1;
    }

    params.seed = coloredSeed;
    if(!startGenerator(params, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    stepGenerator();
    if(!testApp.colored || !imagesEqual(coloredReference, generatorTexture().copyToImage())) {
        std::cerr << generatorName << " did not reproduce the colored render after restarting.\n";
        return 1;
    }
#ifndef PFB_TEST_FUJII
    params.colorLimitGal = 0.1;
    if(!startGenerator(params, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    stepGenerator();
    if(imagesEqual(coloredReference, generatorTexture().copyToImage())) {
        std::cerr << "Galaxies color-limit override did not affect the render.\n";
        return 1;
    }
    params.colorLimitGal = GenParams::R;
    if(!startGenerator(params, error)) {
        std::cerr << error << '\n';
        return 1;
    }
    stepGenerator();
    if(!imagesEqual(coloredReference, generatorTexture().copyToImage())) {
        std::cerr << "Galaxies retained the color-limit override after resetting to Auto.\n";
        return 1;
    }
#endif
    std::cout << generatorName << " restarts reproduce both color modes.\n";
    return 0;
}
