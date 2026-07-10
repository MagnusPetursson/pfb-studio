// gen_fujii.cpp — wraps fujii.cpp (Fujii Attractor) in an anonymous namespace.
// Note: fujii.cpp does NOT call texture.display() in its loop(); we must do it.

#include "preinclude.hpp"
#include "generator.hpp"

namespace {
    #define main fujii_original_main
    #include "../legacy/fujii.cpp"
    #undef main
}

static bool     s_initialized = false;
static bool     s_done        = false;
static uint64_t s_lastSeed    = 0;

bool fujii_start(const GenParams& p, std::string& error) {
    s_done = false;
    error.clear();

    // Reset attractor state for clean restart.
    testApp.screen_width  = (p.outputW > 0) ? std::clamp(p.outputW, 512, 4096) : 2048;
    testApp.screen_height = (p.outputH > 0) ? std::clamp(p.outputH, 512, 4096) : 2048;
    testApp.x = testApp.y = testApp.t = 0;
    testApp.minx = testApp.miny = 10;
    testApp.maxx = testApp.maxy = -10;

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

    // Apply param overrides after setup() (skip if NaN → use generator's random)
    if (!std::isnan(p.velocity) && p.velocity > 0)     testApp.v           = p.velocity;
    if (!std::isnan(p.p)        && p.p >= 0)            testApp.p           = p.p;
    if (!std::isnan(p.q)        && p.q >= 0)            testApp.q           = p.q;
    if (!std::isnan(p.colorLimit) && p.colorLimit > 0)  testApp.color_limit = p.colorLimit;
    if (!std::isnan(p.coefficientScale) || !std::isnan(p.frequencyScale)) {
        double cs = std::isnan(p.coefficientScale) ? 1.0 : p.coefficientScale;
        double fs = std::isnan(p.frequencyScale)   ? 1.0 : p.frequencyScale;
        for (int i = 1; i <= 6; i++) {
            testApp.a[i] *= cs;
            testApp.f[i] *= fs;
        }
    }
    if (p.duration > 0) testApp.timeLimit = p.duration;

    testApp.clock.restart();
    s_lastSeed    = testApp.seed;
    s_initialized = true;
    return true;
}

bool fujii_step() {
    if (!s_initialized || s_done) return false;
    if (testApp.clock.getElapsedTime().asSeconds() >= (float)testApp.timeLimit) {
        s_done = true;
        return false;
    }
    testApp.loop();
    testApp.texture.display(); // fujii.cpp does NOT call display() — we must. ✓
    return true;
}

const sf::Texture& fujii_texture()    { return testApp.texture.getTexture(); }
int  fujii_native_width()             { return testApp.screen_width;  }
int  fujii_native_height()            { return testApp.screen_height; }
uint64_t fujii_last_seed()            { return s_lastSeed; }
