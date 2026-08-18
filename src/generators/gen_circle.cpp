// gen_circle.cpp — wraps circle.cpp (Organic Growth) in an anonymous namespace.
// aural.hpp and all its definitions get internal linkage here, so they don't
// conflict with the identical definitions in gen_fractal.cpp etc.

#include "preinclude.hpp"
#include "generator.hpp"

namespace {
    #define main circle_original_main
    // WINDOW is defined by circle.cpp line 1; we let it be — setup() creates a
    // hidden window, loop() calls texture.display() via #ifdef WINDOW. ✓
    #include "../legacy/circle.cpp"
    #undef main
}

static bool     s_initialized = false;
static bool     s_done        = false;
static bool     s_benchmark   = false;
static uint64_t s_lastSeed    = 0;
static uint64_t s_workUnits   = 0;
static constexpr uint64_t CIRCLE_BENCHMARK_TARGET = 100000000ull;

static uint64_t pairEvaluationsPerStep() {
    uint64_t total = 0;
    for (const auto& colony : testApp.colonies) {
        const uint64_t count = static_cast<uint64_t>(colony.particles.size());
        total += count * count;
    }
    return total;
}

bool circle_start(const GenParams& p, std::string& error) {
    s_done = false;
    s_benchmark = p.benchmarkMode;
    s_workUnits = 0;
    error.clear();

    // Reset mutable state before re-setup so restarts are clean.
    testApp.screen_width  = (p.outputW > 0) ? std::clamp(p.outputW, 512, 4096) : 1800;
    testApp.screen_height = (p.outputH > 0) ? std::clamp(p.outputH, 512, 4096) : 1800;
    testApp.colonies.clear();

    // Dimensions
    if (p.duration > 0) testApp.timeLimit = p.duration;

    testApp.init();
    testApp.window.setVisible(false);

    if (p.seed) {
        testApp.seed = p.seed;
        aural::rnd::seedEngine((unsigned int)p.seed);
        aural::math::initNoise(p.seed);
    } else {
        aural::rnd::seedEngine((unsigned int)testApp.seed);
        aural::math::initNoise(testApp.seed);
    }
    aural::flame::initFlame();
    aural::renderer = &testApp.texture;

    testApp.setup();
    testApp.window.setVisible(false);

    if (p.duration > 0) testApp.timeLimit = p.duration;

    // Apply colony-scale overrides post-setup (skip if NaN → use generator's random)
    for (auto& colony : testApp.colonies) {
        if (!std::isnan(p.colonyScale))      colony.radius      *= p.colonyScale;
        if (!std::isnan(p.proximityScale))   colony.proximity   *= p.proximityScale;
        if (!std::isnan(p.noiseScaleCircle)) colony.noise_scale *= p.noiseScaleCircle;
        if (!std::isnan(p.coordScaleCircle)) colony.coord_scale *= p.coordScaleCircle;
        if (!std::isnan(p.timeStepScale))    colony.time_step   *= p.timeStepScale;
    }

    testApp.clock.restart();
    s_lastSeed    = testApp.seed;
    s_initialized = true;
    return true;
}

bool circle_step() {
    if (!s_initialized || s_done) return false;
    if (!s_benchmark && testApp.clock.getElapsedTime().asSeconds() >= (float)testApp.timeLimit) {
        s_done = true;
        return false;
    }
    const uint64_t evaluationsThisStep = pairEvaluationsPerStep();
    testApp.loop();
    s_workUnits += evaluationsThisStep;
    // texture.display() is inside #ifdef WINDOW in circle.cpp, which is defined,
    // so the loop() call already finalises the texture. ✓
    if (s_benchmark && s_workUnits >= CIRCLE_BENCHMARK_TARGET) {
        s_done = true;
        return false;
    }
    return true;
}

const sf::Texture& circle_texture()    { return testApp.texture.getTexture(); }
int  circle_native_width()             { return testApp.screen_width;  }
uint64_t circle_last_seed()            { return s_lastSeed; }
int  circle_native_height()            { return testApp.screen_height; }
GenPerformance circle_performance() {
    return {s_workUnits, CIRCLE_BENCHMARK_TARGET, "pair evaluations"};
}
