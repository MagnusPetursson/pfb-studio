// gen_galaxies.cpp — wraps galaxies.cpp (Galaxies/Fujii multi-attractor).
// Note: galaxies.cpp does NOT call texture.display() in its loop(); we must do it.

#include "preinclude.hpp"
#include "generator.hpp"

namespace {
    #define main galaxies_original_main
    #include "../legacy/galaxies.cpp"
    #undef main
}

static bool     s_initialized = false;
static bool     s_done        = false;
static uint64_t s_lastSeed    = 0;

bool galaxies_start(const GenParams& p, std::string& error) {
    s_done = false;
    error.clear();

    // Clear attractor list for clean restart.
    testApp.screen_width  = (p.outputW > 0) ? std::clamp(p.outputW, 512, 4096) : 2048;
    testApp.screen_height = (p.outputH > 0) ? std::clamp(p.outputH, 512, 4096) : 2048;
    testApp.attractors.clear();
    testApp.timer = 0;

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

    // Apply post-setup overrides (skip if NaN → use generator's random)
    if (!std::isnan(p.colorLimitGal) && p.colorLimitGal > 0) testApp.color_limit = p.colorLimitGal;
    if (!std::isnan(p.attractorScale)) {
        for (auto& a : testApp.attractors)
            a.radius *= p.attractorScale;
        testApp.bg.radius *= p.attractorScale;
    }
    if (p.duration > 0) testApp.timeLimit = p.duration;

    testApp.clock.restart();
    s_lastSeed    = testApp.seed;
    s_initialized = true;
    return true;
}

bool galaxies_step() {
    if (!s_initialized || s_done) return false;
    if (testApp.clock.getElapsedTime().asSeconds() >= (float)testApp.timeLimit) {
        s_done = true;
        return false;
    }
    testApp.loop();
    testApp.texture.display(); // galaxies.cpp does NOT call display() — we must. ✓
    return true;
}

const sf::Texture& galaxies_texture()    { return testApp.texture.getTexture(); }
int  galaxies_native_width()             { return testApp.screen_width;  }
int  galaxies_native_height()            { return testApp.screen_height; }
uint64_t galaxies_last_seed()            { return s_lastSeed; }
