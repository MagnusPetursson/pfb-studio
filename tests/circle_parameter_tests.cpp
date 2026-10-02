// Include the production wrapper to inspect the particle state actually used
// by its simulation without adding a test-only public generator API.
#include "../src/generators/gen_circle.cpp"

#include <stdexcept>

namespace {

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

void start(const GenParams& params) {
    std::string error;
    require(circle_start(params, error), "Circle startup failed");
    require(error.empty(), "Successful Circle startup reported an error");
    require(circle_performance().workUnits == 0, "Circle startup retained old work");
}

bool equalImages(const sf::Image& first, const sf::Image& second) {
    const auto size = first.getSize();
    return size == second.getSize() &&
        std::memcmp(first.getPixelsPtr(), second.getPixelsPtr(),
                    static_cast<std::size_t>(size.x) * size.y * 4) == 0;
}

void checkOverrides(const std::vector<baseApp::colony>& baseline, double radiusScale, double coordinateScale) {
    require(testApp.colonies.size() == baseline.size(), "Override changed the seeded colony count");
    bool moodChanged = false;
    for (std::size_t c = 0; c < baseline.size(); ++c) {
        const auto& before = baseline[c];
        const auto& after = testApp.colonies[c];
        require(after.radius == before.radius * radiusScale, "Colony radius override was ignored");
        require(after.coord_scale == before.coord_scale * coordinateScale, "Colony coordinate scale override was ignored");
        require(after.particles.size() == before.particles.size(), "Override changed the seeded particle count");
        for (std::size_t p = 0; p < before.particles.size(); ++p) {
            const auto& original = before.particles[p];
            const auto& particle = after.particles[p];
            require(particle.radius == after.radius, "Particle reset still uses the original colony radius");
            require(particle.coord_scale == after.coord_scale, "Particle mood still uses the original coordinate scale");
            const double expectedX = radiusScale == 1.0 ? original.pos.x :
                after.centerx + (original.pos.x - after.centerx) * radiusScale;
            const double expectedY = radiusScale == 1.0 ? original.pos.y :
                after.centery + (original.pos.y - after.centery) * radiusScale;
            require(particle.pos.x == expectedX && particle.pos.y == expectedY,
                    "Colony scale was not applied to the initial particle positions");
            auto recalculated = particle;
            recalculated.calcMood(after.t);
            require(particle.mood == recalculated.mood, "Initial particle mood was not refreshed after override");
            moodChanged = moodChanged || particle.mood != original.mood;
        }
    }
    if (radiusScale != 1.0 || coordinateScale != 1.0)
        require(moodChanged, "Overrides did not affect any initial particle mood");
}

void runTests() {
    GenParams original;
    original.seed = 424242;
    original.outputW = original.outputH = 512;
    original.benchmarkMode = true;
    start(original);
    const auto baseline = testApp.colonies;
    const auto randomState = au::rnd::engine;
    require(!baseline.empty() && !baseline.front().particles.empty(), "Circle created no particles");
    require(circle_step(), "Baseline Circle step stopped unexpectedly");
    const auto baselineAfterStep = testApp.colonies;
    const auto baselineImage = circle_texture().copyToImage();

    GenParams scaled = original;
    scaled.coordScaleCircle = 2.0;
    start(scaled);
    require(au::rnd::engine == randomState, "Coordinate override consumed extra random samples");
    checkOverrides(baseline, 1.0, 2.0);
    require(circle_step(), "Coordinate-scaled Circle step stopped unexpectedly");
    bool motionChanged = false;
    for (std::size_t c = 0; c < testApp.colonies.size(); ++c)
        for (std::size_t p = 0; p < testApp.colonies[c].particles.size(); ++p) {
            const auto& actual = testApp.colonies[c].particles[p].pos;
            const auto& before = baselineAfterStep[c].particles[p].pos;
            motionChanged = motionChanged || actual.x != before.x || actual.y != before.y;
        }
    require(motionChanged, "Coordinate scale did not affect the production simulation");

    scaled = original;
    scaled.colonyScale = 0.5;
    start(scaled);
    require(au::rnd::engine == randomState, "Radius override consumed extra random samples");
    checkOverrides(baseline, 0.5, 1.0);

    // Exercise the actual particle respawn code with a matched random stream.
    auto actual = testApp.colonies.front().particles.front();
    auto expected = baseline.front().particles.front();
    expected.radius *= 0.5;
    au::rnd::seedEngine(987654u);
    actual.reset(0.0);
    au::rnd::seedEngine(987654u);
    expected.reset(0.0);
    require(actual.pos.x == expected.pos.x && actual.pos.y == expected.pos.y && actual.mood == expected.mood,
            "Particle respawn did not retain the scaled radius");

    scaled.coordScaleCircle = 1.75;
    start(scaled);
    checkOverrides(baseline, 0.5, 1.75);

    // Identity overrides preserve exact seeded behavior, including RNG state.
    scaled.colonyScale = scaled.coordScaleCircle = 1.0;
    start(scaled);
    require(au::rnd::engine == randomState, "Identity overrides changed the random state");
    checkOverrides(baseline, 1.0, 1.0);
    require(circle_step(), "Identity-scaled Circle step stopped unexpectedly");
    require(equalImages(baselineImage, circle_texture().copyToImage()), "Identity overrides changed seeded pixels");

    start(original);
    require(au::rnd::engine == randomState, "Reset changed the seeded random state");
    checkOverrides(baseline, 1.0, 1.0);
    require(circle_step(), "Replay Circle step stopped unexpectedly");
    require(equalImages(baselineImage, circle_texture().copyToImage()), "Reset retained Circle overrides");
}

} // namespace

int main() {
    try {
        runTests();
        std::cout << "Circle parameter propagation tests passed\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
