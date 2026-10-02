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

#ifndef PFB_TEST_FUJII
// Reference the original full calculation, including the invisible prefix, so
// removing warm-up arithmetic cannot silently change RNG or later geometry.
std::vector<sf::Vertex> referenceGalaxyIteration(baseApp::attractor& a) {
    std::vector<sf::Vertex> vertices;
    const int iterations = static_cast<int>(10000 * map(a.radius, 80, 800, 0.2, 1));
    for(int i = 1; i <= iterations; ++i) {
        double xx = a.x, yy = a.y;
        xx = a.a[1]*ssin(a.f[1]*a.x, a.p) + a.a[2]*ccos(a.f[2]*a.y, a.q) + a.a[3]*ssin(a.f[3]*a.t, a.p);
        yy = a.a[4]*ccos(a.f[4]*a.x, a.q) + a.a[5]*ssin(a.f[5]*a.y, a.p) + a.a[6]*ssin(a.f[6]*a.t, a.q);
        a.t += a.v;
        vec step(xx-a.x, yy-a.y);
        step = step*10;
        const double amount = constrain(map(step.mag2(), 0, M_PI*M_PI*2, 0, 1), -a.color_limit, a.color_limit);
        sf::Color color = interpolate(a.colors[0], a.colors[1], amount);
        color.a = 10 * gaussian(1, 0.1);
        a.x = xx;
        a.y = yy;
        a.minx = std::min(a.minx, a.x);
        a.miny = std::min(a.miny, a.y);
        a.maxx = std::max(a.maxx, a.x);
        a.maxy = std::max(a.maxy, a.y);
        xx = map(a.x, a.minx, a.maxx, -1, 1);
        yy = map(a.y, a.miny, a.maxy, -1, 1);
        double xxx = xx * sqrt(1-(yy*yy)/2);
        double yyy = yy * sqrt(1-(xx*xx)/2);
        xxx *= a.radius;
        yyy *= a.radius;
        xxx += a.centerx;
        yyy += a.centery;
        vec radial = vec(xxx, yyy) - vec(a.centerx, a.centery);
        color.a *= map(radial.mag(), 0, a.radius, 0, 1);
        if(i > 2000) {
            const float left = static_cast<float>(xxx);
            const float top = static_cast<float>(yyy);
            vertices.emplace_back(sf::Vector2f(left, top), color);
            vertices.emplace_back(sf::Vector2f(left + 1.f, top), color);
            vertices.emplace_back(sf::Vector2f(left + 1.f, top + 1.f), color);
            vertices.emplace_back(sf::Vector2f(left, top + 1.f), color);
        }
    }
    return vertices;
}

bool checkGalaxyWarmup() {
    // Cover fewer than, exactly, and more than 2000 iterations, including the
    // large background attractor. Repeated calls also check learned bounds.
    for(const unsigned seed : {1u, 424242u, 987654u}) {
        for(const double radius : {75.0, 80.0, 81.0, 600.0, 1200.0}) {
            aural::rnd::seedEngine(seed);
            baseApp::attractor expected(128, 128, radius);
            expected.create();
            expected.colors[0] = sf::Color(37, 71, 181);
            expected.colors[1] = sf::Color(233, 109, 43);
            auto actual = expected;
            for(int iteration = 0; iteration < 2; ++iteration) {
                const auto initialEngine = aural::rnd::engine;
                const auto vertices = referenceGalaxyIteration(expected);
                const auto expectedEngine = aural::rnd::engine;
                aural::rnd::engine = initialEngine;
                actual.iterate(512, 512, iteration == 0);
                if(aural::rnd::engine != expectedEngine || actual.x != expected.x || actual.y != expected.y ||
                   actual.t != expected.t || actual.minx != expected.minx || actual.miny != expected.miny ||
                   actual.maxx != expected.maxx || actual.maxy != expected.maxy ||
                   actual.pointBatch.size() != vertices.size()) return false;
                for(std::size_t i = 0; i < vertices.size(); ++i)
                    if(actual.pointBatch[i].position != vertices[i].position ||
                       actual.pointBatch[i].color != vertices[i].color) return false;
            }
        }
    }
    return true;
}
#endif
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
        if(testApp.present_window || !testApp.defer_initial_window || !testApp.window.isOpen()) {
            std::cerr << generatorName << " benchmark window setup is incorrect.\n";
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
    if(!checkGalaxyWarmup()) {
        std::cerr << "Galaxies warm-up changed the RNG, motion, bounds, or visible vertices.\n";
        return 1;
    }
#endif
    params.benchmarkMode = false;
    if(!startGenerator(params, error) || !testApp.present_window || !testApp.window.isOpen()) {
        std::cerr << generatorName << " did not restore normal window presentation after benchmarking.\n";
        return 1;
    }
    params.benchmarkMode = true;
    if(!startGenerator(params, error) || testApp.present_window) {
        std::cerr << generatorName << " did not disable window presentation when restarting a benchmark.\n";
        return 1;
    }
    std::cout << generatorName << " restarts reproduce both color modes.\n";
    return 0;
}
