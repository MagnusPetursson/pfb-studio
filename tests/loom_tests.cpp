#include "generator.hpp"

#include <SFML/System.hpp>

#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
constexpr uint64_t expectedTarget = 1179648;

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

bool imagesEqual(const sf::Image& first, const sf::Image& second) {
    const auto size = first.getSize();
    return size == second.getSize() && size.x > 0 && size.y > 0 &&
        std::memcmp(first.getPixelsPtr(), second.getPixelsPtr(),
            static_cast<std::size_t>(size.x) * size.y * 4) == 0;
}

void start(const GenParams& params) {
    std::string error = "stale error";
    const bool started = loom_start(params, error);
    require(started, "Loom startup failed: " + error);
    require(error.empty(), "Successful startup retained an error.");
    require(loom_performance().workUnits == 0, "Startup retained previous work.");
    require(loom_performance().benchmarkTarget == expectedTarget, "Unexpected Loom work target.");
    require(loom_last_seed() != 0, "Startup did not expose a replayable seed.");
    if (params.seed) require(loom_last_seed() == params.seed, "Startup changed the requested seed.");
    const int expectedWidth = params.outputW == -1 ? 2048 : params.outputW;
    const int expectedHeight = params.outputH == -1 ? 2048 : params.outputH;
    require(loom_native_width() == expectedWidth && loom_native_height() == expectedHeight,
            "Reported dimensions differ from the requested canvas.");
    require(loom_texture().getSize() == sf::Vector2u(expectedWidth, expectedHeight),
            "Render texture dimensions differ from the requested canvas.");
}

sf::Image advancePrefix() {
    for (unsigned tick = 0; tick < 4; ++tick) {
        require(loom_step(), "Loom stopped before completing the test prefix.");
        require(loom_performance().workUnits == (tick + 1) * 8192,
                "Loom prefix did not account for every field step.");
    }
    return loom_texture().copyToImage();
}

sf::Image prefix(const GenParams& params) {
    start(params);
    return advancePrefix();
}

sf::Image finish() {
    sf::Clock timeout;
    uint64_t previousWork = loom_performance().workUnits;
    bool running = true;
    while (running) {
        require(timeout.getElapsedTime().asSeconds() < 120.f, "Loom did not finish its finite composition.");
        running = loom_step();
        const auto work = loom_performance().workUnits;
        require(work > previousWork && work <= expectedTarget, "Loom made no progress or exceeded its work target.");
        previousWork = work;
    }
    require(previousWork == expectedTarget, "Loom stopped before completing the composition.");
    const auto image = loom_texture().copyToImage();
    require(!loom_step() && !loom_step(), "Completed Loom generation resumed unexpectedly.");
    require(loom_performance().workUnits == expectedTarget, "Completed generation changed its work count.");
    require(imagesEqual(image, loom_texture().copyToImage()), "Completed generation changed its pixels.");
    return image;
}

void expectRejected(const GenParams& params) {
    std::string error = "stale error";
    require(!loom_start(params, error), "Loom accepted invalid parameters.");
    require(!error.empty() && error != "stale error", "Invalid parameters lacked a specific error.");
    require(!loom_step() && loom_performance().workUnits == 0,
            "A failed start left the previous generation running.");
}

void checkValidation(const GenParams& base) {
    // A failed restart must stop an active generation, not continue with its
    // old settings. Remaining rejected starts also exercise the stopped state.
    start(base);
    require(loom_step(), "Could not establish an active generation for validation.");
    GenParams invalid = base;
    invalid.outputW = 63;
    expectRejected(invalid);
    for (int GenParams::*member : {&GenParams::outputW, &GenParams::outputH}) {
        for (const int value : {-2, 0, 63, 4097}) {
            invalid = base;
            invalid.*member = value;
            expectRejected(invalid);
        }
    }
    for (const int value : {-2, 0, 1, 11}) {
        invalid = base;
        invalid.loomSymmetry = value;
        expectRejected(invalid);
    }
    const double infinity = std::numeric_limits<double>::infinity();
    for (const double value : {-2.0, 0.0, infinity, -infinity, GenParams::R}) {
        invalid = base;
        invalid.duration = value;
        expectRejected(invalid);
    }
    struct Range { double GenParams::*member; double low, high; };
    for (const auto range : {
            Range{&GenParams::loomTurbulence, 0, 1}, Range{&GenParams::loomTwist, -1, 1},
            Range{&GenParams::loomSpread, .4, 1.4}, Range{&GenParams::loomHue, 0, 360},
            Range{&GenParams::loomExposure, .25, 2}}) {
        for (const double value : {range.low - .01, range.high + .01, infinity, -infinity}) {
            invalid = base;
            invalid.*range.member = value;
            expectRejected(invalid);
        }
    }
}

void runTests() {
    GenParams base;
    base.seed = 424242;
    base.outputW = 256;
    base.outputH = 192;
    base.benchmarkMode = true;
    // Benchmark work must ignore a budget which has already expired.
    base.duration = .000001;
    start(base);
    const auto background = loom_texture().copyToImage();
    sf::sleep(sf::milliseconds(2));
    const auto expectedPrefix = advancePrefix();
    const auto expected = finish();
    require(!imagesEqual(background, expected), "Completed Loom output contains only its setup background.");

    auto alternate = base;
    alternate.seed = (1ull << 40) | base.seed;
    require(!imagesEqual(expectedPrefix, prefix(alternate)), "The upper seed bits did not affect the composition.");
    alternate = base;
    alternate.loomSymmetry = 2;
    require(!imagesEqual(expectedPrefix, prefix(alternate)), "Symmetry did not affect the drawn threads.");
    struct Override { double GenParams::*member; double value; const char* name; };
    for (const auto overrideValue : {
            Override{&GenParams::loomTurbulence, 1, "Turbulence"},
            Override{&GenParams::loomTwist, -1, "Twist"},
            Override{&GenParams::loomSpread, 1.4, "Spread"},
            Override{&GenParams::loomHue, 0, "Hue"},
            Override{&GenParams::loomExposure, 2, "Exposure"}}) {
        alternate = base;
        alternate.*overrideValue.member = overrideValue.value;
        require(!imagesEqual(expectedPrefix, prefix(alternate)),
                std::string(overrideValue.name) + " did not affect the drawn threads.");
    }

    require(imagesEqual(expectedPrefix, prefix(base)), "Resetting parameters to Auto retained previous overrides.");
    require(imagesEqual(expected, finish()), "Replaying the seed changed the completed benchmark image.");

    auto normal = base;
    normal.benchmarkMode = false;
    normal.duration = 120;
    start(normal);
    require(imagesEqual(expected, finish()), "Normal completion differed from fixed-work completion.");

    normal.duration = .000001;
    start(normal);
    sf::sleep(sf::milliseconds(2));
    require(!loom_step() && loom_performance().workUnits == 0,
            "An expired normal time budget still performed field work.");

    auto automatic = base;
    automatic.seed = 0;
    const auto automaticImage = prefix(automatic);
    automatic.seed = loom_last_seed();
    require(imagesEqual(automaticImage, prefix(automatic)), "An automatic seed could not be replayed.");

    auto dimensions = base;
    for (const auto size : {sf::Vector2i(64, 64), sf::Vector2i(4096, 64),
                           sf::Vector2i(64, 4096), sf::Vector2i(-1, -1)}) {
        dimensions.outputW = size.x;
        dimensions.outputH = size.y;
        start(dimensions);
    }
    auto endpoints = base;
    endpoints.loomSymmetry = 10;
    endpoints.loomTurbulence = 0;
    endpoints.loomTwist = 1;
    endpoints.loomSpread = .4;
    endpoints.loomHue = 360;
    endpoints.loomExposure = .25;
    endpoints.duration = -1;
    prefix(endpoints);
    checkValidation(base);
}
} // namespace

int main() {
    try {
        runTests();
        std::cout << "Magnetic Loom replay, parameters, work limits, and validation passed.\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Magnetic Loom test failed: " << error.what() << '\n';
        return 1;
    }
}
