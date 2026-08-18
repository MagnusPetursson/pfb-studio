// gen_fractal.cpp — wraps fractal.cpp (Fractal Flame) in an anonymous namespace.

#include "preinclude.hpp"
#include "generator.hpp"

namespace {
    #define main fractal_original_main
    #include "../legacy/fractal.cpp"
    #undef main
}

static bool     s_initialized = false;
static bool     s_done        = false;
static bool     s_benchmark   = false;
static uint64_t s_lastSeed    = 0;
static uint64_t s_workUnits   = 0;
static constexpr uint64_t FRACTAL_BENCHMARK_TARGET = 10000000ull;

bool fractal_start(const GenParams& p, std::string& error) {
    s_done = false;
    s_benchmark = p.benchmarkMode;
    s_workUnits = 0;
    error.clear();

    // Clear mutable state for clean restart.
    testApp.screen_width  = (p.outputW > 0) ? std::clamp(p.outputW, 512, 2000) : 2000;
    testApp.screen_height = (p.outputH > 0) ? std::clamp(p.outputH, 512, 2000) : 2000;
    testApp.fractals.clear();
    testApp.preprocess  = 1;
    testApp.blur_pass   = 1;
    testApp.t           = 0;
    testApp.t_max       = 0;
    testApp.cur_it      = 1;
    testApp.preprocess_time = 8;
    testApp.max_hits    = 0;
    testApp.temp_hits   = 0;
    testApp.hue_override = !std::isnan(p.fractalHue)
        ? std::clamp((int)std::round(p.fractalHue), 0, 360)
        : -1;
    std::memset(testApp.hits, 0, sizeof(testApp.hits));

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
    if (!testApp.blur_loaded) {
        error = "The fractal blur shader could not be compiled.";
        return false;
    }

    if (!std::isnan(p.preprocessTime) && p.preprocessTime > 0) testApp.preprocess_time = p.preprocessTime;
    if (p.fractalBlurSet) testApp.blur_pass = p.fractalBlur ? 1 : 0;
    if (p.duration > 0) testApp.timeLimit = p.duration;

    testApp.clock.restart();
    s_lastSeed    = testApp.seed;
    s_initialized = true;
    return true;
}

bool fractal_step() {
    if (!s_initialized || s_done) return false;
    if (!s_benchmark && testApp.clock.getElapsedTime().asSeconds() >= (float)testApp.timeLimit) {
        s_done = true;
        return false;
    }
    const uint64_t iterationsThisStep = static_cast<uint64_t>(testApp.fractals.size()) * 3000ull;
    testApp.loop();
    s_workUnits += iterationsThisStep;
    // fractal.cpp calls texture.display() unconditionally on line 363. ✓
    if (s_benchmark && s_workUnits >= FRACTAL_BENCHMARK_TARGET) {
        s_done = true;
        return false;
    }
    return true;
}

const sf::Texture& fractal_texture()    { return testApp.texture.getTexture(); }
int  fractal_native_width()             { return testApp.screen_width;  }
int  fractal_native_height()            { return testApp.screen_height; }
uint64_t fractal_last_seed()            { return s_lastSeed; }
GenPerformance fractal_performance() {
    return {s_workUnits, FRACTAL_BENCHMARK_TARGET, "flame iterations"};
}
