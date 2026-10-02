#include "preinclude.hpp"
#include <stdexcept>

namespace {
#define main fractal_original_main
#include "../src/legacy/fractal.cpp"
#undef main

void require(bool condition, const char* message) {
    if(!condition) throw std::runtime_error(message);
}

int referenceSelection(const std::vector<double>& weights, double r) {
    double cumulative = 0;
    for(std::size_t i = 0; i < weights.size(); ++i) {
        cumulative += weights[i];
        if(r <= cumulative) return static_cast<int>(i);
    }
    return 0;
}

// The original map-dispatch path is the oracle. Keep its coefficient writes,
// summation order, and zero-weight calls: some variations consume randomness.
vec referenceFunction(const baseApp::func& f, vec v) {
    flame::A = f.c[0];
    flame::B = f.c[1];
    flame::C = f.c[2];
    flame::D = f.c[3];
    flame::B = f.c[4];
    flame::B = f.c[5];
    const vec transformed = affine(v, f.c);
    vec result(0, 0);
    for(std::size_t i = 0; i < f.id.size(); ++i)
        result = result + variations[f.id[i]](transformed, f.w[i]);
    return affinePost(result, f.p);
}

void checkFunction(baseApp::fractal& value, int index, vec input) {
    const auto initialRandomState = au::rnd::engine;
    const auto expected = referenceFunction(value.funcs[index], input);
    const auto expectedRandomState = au::rnd::engine;
    au::rnd::engine = initialRandomState;
    const auto actual = value.runFunc(input, index);
    require(std::memcmp(&actual.x, &expected.x, sizeof(double)) == 0 &&
            std::memcmp(&actual.y, &expected.y, sizeof(double)) == 0,
            "Cached Fractal dispatch changed the output bits");
    require(au::rnd::engine == expectedRandomState,
            "Cached Fractal dispatch changed random-number consumption");
}

void checkWeights(const std::vector<double>& weights) {
    baseApp::fractal value(0, {});
    value.weights = weights;
    const auto initialRandomState = au::rnd::engine;
    value.cacheWeights();
    require(au::rnd::engine == initialRandomState, "Caching weights consumed randomness");
    std::vector<double> boundaries = {0.0, 1.0};
    double cumulative = 0;
    for(double weight : weights) {
        cumulative += weight;
        boundaries.push_back(cumulative);
        boundaries.push_back(std::nextafter(cumulative, -std::numeric_limits<double>::infinity()));
        boundaries.push_back(std::nextafter(cumulative, std::numeric_limits<double>::infinity()));
    }
    for(double boundary : boundaries)
        require(value.selectFunction(boundary) == referenceSelection(weights, boundary),
                "Cached weights changed a selection boundary or fallback");

    std::vector<int> expected;
    for(int i = 0; i < 2000; ++i)
        expected.push_back(referenceSelection(weights, au::rnd::random(1.0)));
    const auto expectedRandomState = au::rnd::engine;
    au::rnd::engine = initialRandomState;
    for(int choice : expected)
        require(value.weightedRand() == choice, "Cached weights changed seeded selections");
    require(au::rnd::engine == expectedRandomState, "Cached selection changed the random state");
}

void runTests() {
    for(unsigned seed : {1u, 424242u, 987654u}) {
        au::rnd::seedEngine(seed);
        au::math::initNoise(seed);
        au::flame::initFlame();
        std::vector<std::string> names;
        for(const auto& entry : variations) names.push_back(entry.first);

        baseApp::fractal value(123, names);
        value.initialize(10.0);
        for(double time : {0.0, 5.0, 100.0}) {
            if(time != 0) value.randomiseCoeffs(time);
            for(std::size_t i = 0; i < value.funcs.size(); ++i)
                for(const vec input : {vec(0.25, -0.5), vec(0.7, 0.9), vec(-1.2, 0.3), vec(0, 0)})
                    checkFunction(value, static_cast<int>(i), input);
        }
        checkWeights(value.weights);
        checkWeights({0, 0, 0.25, 0, 0.5, 0});
        checkWeights({0, 0, 0});
        checkWeights({0.1, 0.2, 0.3});
        checkWeights({});

        // Exercise every registered variation, including random variations
        // with zero contribution that must still be called in the same order.
        baseApp::fractal allVariations(0, {});
        std::vector<double> weights(names.size(), 0);
        for(std::size_t i = 1; i < weights.size(); i += 2) weights[i] = 0.25;
        const auto initialRandomState = au::rnd::engine;
        allVariations.funcs.emplace_back(names, weights,
            std::vector<double>{0.7, 0.2, 0.3, -0.1, 0.8, 0.4}, sf::Color::White,
            std::vector<double>{0, 0.1, -0.2, 0, 0, 0}, 1);
        require(au::rnd::engine == initialRandomState, "Caching variation pointers consumed randomness");
        checkFunction(allVariations, 0, vec(0.25, -0.5));
    }
}
}

int main() {
    try {
        runTests();
        std::cout << "Fractal dispatch and weight caches preserve output bits and random state.\n";
    } catch(const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
