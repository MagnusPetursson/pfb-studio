#include "generator.hpp"

#include <algorithm>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void start(const GenParams& params) {
    std::string error;
    if (!perlin_start(params, error))
        throw std::runtime_error("Perlin startup failed: " + error);
    require(error.empty(), "Successful startup should clear the error");
    require(perlin_last_seed() == params.seed, "Reported seed differs from requested seed");
    require(perlin_performance().workUnits == 0, "Startup must reset accumulated work");
}

bool equalImages(const sf::Image& first, const sf::Image& second) {
    const auto size = first.getSize();
    return size == second.getSize() &&
        std::memcmp(first.getPixelsPtr(), second.getPixelsPtr(),
                    static_cast<std::size_t>(size.x) * size.y * 4) == 0;
}

void requireGrayscale(const sf::Image& image) {
    const auto size = image.getSize();
    const auto* pixels = image.getPixelsPtr();
    for (std::size_t offset = 0; offset < static_cast<std::size_t>(size.x) * size.y * 4; offset += 4)
        require(pixels[offset] == pixels[offset + 1] && pixels[offset] == pixels[offset + 2],
                "Monochrome output contains colored pixels");
}

sf::Image renderOneStep(const GenParams& params) {
    start(params);
    require(perlin_step(), "First step ended unexpectedly");
    require(perlin_performance().workUnits > 0, "Step performed no particle updates");
    return perlin_texture().copyToImage();
}

void testMonochromeFirstRun() {
    GenParams params;
    params.seed = 314159;
    params.aspect = 3;
    params.customAspectW = 96;
    params.customAspectH = 64;
    params.duration = 60;
    params.coloredSet = true;
    params.colored = false;
    start(params);
    const auto background = perlin_texture().copyToImage();
    requireGrayscale(background);
    require(perlin_step(), "Monochrome first step ended unexpectedly");
    const auto rendered = perlin_texture().copyToImage();
    requireGrayscale(rendered);
    require(!equalImages(background, rendered), "Monochrome step did not draw any particles");
    require(equalImages(rendered, renderOneStep(params)), "Monochrome seed replay changed pixels");
}

void testAspectAndDensity() {
    GenParams params;
    params.aspect = 3;
    params.customAspectW = 96;
    params.customAspectH = 64;
    params.duration = 60;
    // Different seeds can choose different original aspects. The explicit
    // custom aspect must always use the same six-unit-square particle domain.
    for (const auto seed : {1ull, 42ull, 314159ull, 271828ull}) {
        params.seed = seed;
        renderOneStep(params);
        require(perlin_native_width() == 96 && perlin_native_height() == 64,
                "Custom canvas dimensions were ignored");
        require(perlin_performance().workUnits == 29584,
                "Custom aspect retained particles from the random aspect");
    }

    params.density = 0.25;
    renderOneStep(params);
    require(perlin_performance().workUnits == 1849,
            "Density override was not applied to the final particle domain");
}

void testResetAndReplay() {
    GenParams original;
    original.seed = 42;
    original.duration = 60;
    const auto expected = renderOneStep(original);
    const auto expectedWork = perlin_performance().workUnits;
    const auto expectedWidth = perlin_native_width();
    const auto expectedHeight = perlin_native_height();
    require(expectedWidth == 2048 && (expectedHeight == 2048 || expectedHeight == 1152),
            "Original aspect retained a previous custom canvas");

    GenParams overridden;
    overridden.seed = 271828;
    overridden.aspect = 3;
    overridden.customAspectW = 128;
    overridden.customAspectH = 80;
    overridden.duration = 60;
    overridden.density = 0.25;
    overridden.flowSpeed = 0.008;
    overridden.smoothing = 0.8;
    overridden.fieldWeight = 0.4;
    overridden.hue = 75;
    overridden.coloredSet = true;
    overridden.colored = false;
    overridden.contrast = 0.6;
    overridden.flowPreset = 3;
    overridden.coordScale = 120;
    overridden.noiseScale = 25;
    renderOneStep(overridden);

    const auto replay = renderOneStep(original);
    require(perlin_native_width() == expectedWidth && perlin_native_height() == expectedHeight,
            "Reset did not restore the original seeded canvas");
    require(perlin_performance().workUnits == expectedWork,
            "Reset retained the previous density");
    require(equalImages(expected, replay), "Reset retained prior overrides or changed seed replay");
}

void testFailedStartStopsPreviousRun() {
    GenParams params;
    params.seed = 42;
    params.aspect = 3;
    params.customAspectW = params.customAspectH = 64;
    params.duration = 60;
    start(params);

    for (const auto density : {0.0, -1.0, std::numeric_limits<double>::infinity()}) {
        params.density = density;
        std::string error;
        require(!perlin_start(params, error), "Invalid density was accepted");
        require(!error.empty(), "Invalid density should report an error");
        require(!perlin_step(), "Failed startup left the previous run active");
    }
    params.density = GenParams::R;
    params.flowPreset = FLOW_PRESET_COUNT;
    std::string error;
    require(!perlin_start(params, error), "Invalid preset index was accepted");
    require(!error.empty(), "Invalid preset should report an error");
    require(!perlin_step(), "Invalid preset left a run active");
}

} // namespace

int main() {
    try {
        require(!perlin_step(), "Step ran before startup");
        testMonochromeFirstRun();
        testAspectAndDensity();
        testResetAndReplay();
        testFailedStartStopsPreviousRun();
        std::cout << "Perlin regression tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
