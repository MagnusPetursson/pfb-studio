// Magnetic Loom: softened dipole fields traced as luminous, tapered filaments.
// This is an artistic field, not a physical magnetism simulation.
#include "generator.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <exception>
#include <random>
#include <vector>

namespace {
constexpr double PI = 3.14159265358979323846;
constexpr uint64_t WORK_TARGET = 1179648;
constexpr unsigned STEPS_PER_TICK = 8192;
constexpr unsigned STRAND_LENGTH = 384;
constexpr std::size_t WALK_COUNT = 128;

struct Vec {
    double x = 0, y = 0;
    Vec operator+(Vec b) const { return {x + b.x, y + b.y}; }
    Vec operator-(Vec b) const { return {x - b.x, y - b.y}; }
    Vec operator*(double n) const { return {x * n, y * n}; }
};
double lengthSquared(Vec v) { return v.x * v.x + v.y * v.y; }
Vec unit(Vec v) {
    const double magnitude = std::sqrt(lengthSquared(v));
    return magnitude > 1e-12 ? v * (1.0 / magnitude) : Vec{};
}

struct Pole { Vec position; double charge; };
struct Walk {
    Vec position;
    sf::Color color;
    unsigned age = STRAND_LENGTH;
    double direction = 1;
    double brightness = 1;
};
struct Loom {
    sf::RenderTexture canvas;
    sf::Clock clock;
    std::mt19937_64 random;
    std::vector<Pole> poles;
    std::array<Walk, WALK_COUNT> walks{};
    std::vector<sf::Vertex> glow, threads;
    uint64_t seed = 0, work = 0;
    int width = 0, height = 0, symmetry = 5;
    double turbulence = .35, twist = .3, spread = .9, hue = 190, exposure = 1;
    double phase = 0, curlPhase = 0, rotationCos = 1, rotationSin = 0;
    double scale = 1, duration = 30;
    bool running = false, benchmark = false;

    // Specify the conversion instead of relying on library-specific distributions.
    double sample() { return static_cast<double>(random() >> 11) * 0x1.0p-53; }
    double choose(double supplied, double generated) {
        return std::isnan(supplied) ? generated : supplied;
    }

    Vec field(Vec p) const {
        Vec force;
        for (const auto& pole : poles) {
            const Vec delta = p - pole.position;
            force = force + delta * (pole.charge / (lengthSquared(delta) + .012));
        }
        // Rotate the source/sink field into spirals, then add a smooth curl.
        const Vec rotated{force.x * rotationCos - force.y * rotationSin,
                          force.x * rotationSin + force.y * rotationCos};
        const double a = 4.0 * p.x + curlPhase;
        const double b = 4.0 * p.y - curlPhase;
        const Vec curl{std::sin(a) * std::cos(b), -std::cos(a) * std::sin(b)};
        return unit(rotated + curl * (turbulence * 3.5));
    }

    sf::Vector2f pixel(Vec p) const {
        return {static_cast<float>(width * .5 + p.x * scale),
                static_cast<float>(height * .5 + p.y * scale)};
    }
};
Loom& loom() { static Loom state; return state; }

sf::Uint8 byte(double value) {
    return static_cast<sf::Uint8>(std::clamp(value, 0.0, 255.0));
}
sf::Color hsv(double hue, double saturation, double value) {
    hue = std::fmod(hue + 720.0, 360.0) / 60.0;
    const int sector = static_cast<int>(hue);
    const double f = hue - sector;
    const double p = value * (1 - saturation);
    const double q = value * (1 - f * saturation);
    const double t = value * (1 - (1 - f) * saturation);
    const std::array<std::array<double, 3>, 6> colors{{
        {value, t, p}, {q, value, p}, {p, value, t},
        {p, q, value}, {t, p, value}, {value, p, q}
    }};
    const auto& rgb = colors[sector % 6];
    return {byte(rgb[0] * 255), byte(rgb[1] * 255), byte(rgb[2] * 255)};
}

void spawn(Loom& s, Walk& walk) {
    // Nearby starts trace related paths, creating silk-like families of curves.
    const double angle = s.sample() * 2 * PI;
    const double radius = std::sqrt(.025 + s.sample() * .92) * s.spread;
    walk.position = {std::cos(angle) * radius, std::sin(angle) * radius};
    walk.direction = s.sample() < .5 ? -1 : 1;
    walk.age = 0;
    const double band = .5 + .5 * std::sin(angle * s.symmetry + radius * 5 + s.phase);
    const double hue = s.hue + (band > .58 ? 210 : 0) + s.sample() * 24 - 12;
    const double saturation = .42 + .34 * s.sample();
    const double value = .8 + .2 * s.sample();
    walk.color = hsv(hue, saturation, value);
    walk.brightness = .45 + .55 * s.sample();
}

void triangle(std::vector<sf::Vertex>& vertices, sf::Vector2f a, sf::Vector2f b,
              sf::Vector2f c, sf::Color ca, sf::Color cb, sf::Color cc) {
    vertices.emplace_back(a, ca);
    vertices.emplace_back(b, cb);
    vertices.emplace_back(c, cc);
}

// A bright center fading to transparent edges gives antialiased ribbons at
// every output size without shaders, per-strand textures, or a blur readback.
void ribbon(std::vector<sf::Vertex>& vertices, sf::Vector2f a, sf::Vector2f b,
            float halfWidth, sf::Color color) {
    const sf::Vector2f delta = b - a;
    const float length = std::sqrt(delta.x * delta.x + delta.y * delta.y);
    if (length < 1e-6f) return;
    const sf::Vector2f normal(-delta.y * halfWidth / length, delta.x * halfWidth / length);
    sf::Color edge = color;
    edge.a = 0;
    triangle(vertices, a, b, a + normal, color, color, edge);
    triangle(vertices, a + normal, b, b + normal, edge, color, edge);
    triangle(vertices, a - normal, b - normal, a, edge, edge, color);
    triangle(vertices, a, b - normal, b, color, edge, color);
}

bool parameter(double value, double minimum, double maximum) {
    return std::isnan(value) || (std::isfinite(value) && value >= minimum && value <= maximum);
}

bool validate(const GenParams& p, std::string& error) {
    const auto dimension = [](int v) { return v == -1 || (v >= 64 && v <= 4096); };
    if (!dimension(p.outputW) || !dimension(p.outputH))
        error = "Magnetic Loom output dimensions must be between 64 and 4096.";
    else if (p.duration != -1 && (!std::isfinite(p.duration) || p.duration <= 0))
        error = "Magnetic Loom time budget must be finite and greater than zero.";
    else if (p.loomSymmetry != -1 && (p.loomSymmetry < 2 || p.loomSymmetry > 10))
        error = "Magnetic Loom symmetry must be between 2 and 10.";
    else if (!parameter(p.loomTurbulence, 0, 1) || !parameter(p.loomTwist, -1, 1) ||
             !parameter(p.loomSpread, .4, 1.4) || !parameter(p.loomHue, 0, 360) ||
             !parameter(p.loomExposure, .25, 2))
        error = "Magnetic Loom parameters are outside their supported ranges.";
    return error.empty();
}

void background(Loom& s) {
    s.canvas.clear(sf::Color(3, 5, 10));
    // Low light at the center leaves room for additive threads to build up.
    constexpr unsigned slices = 96;
    sf::VertexArray halo(sf::TriangleFan, slices + 2);
    halo[0] = sf::Vertex(s.pixel({0, 0}), hsv(s.hue, .65, .065));
    for (unsigned i = 0; i <= slices; ++i) {
        const double angle = 2 * PI * i / slices;
        halo[i + 1] = sf::Vertex(s.pixel({1.45 * std::cos(angle), 1.45 * std::sin(angle)}),
                                 sf::Color(3, 5, 10));
    }
    s.canvas.draw(halo);
    s.canvas.display();
}
} // namespace

bool loom_start(const GenParams& p, std::string& error) {
    auto& s = loom();
    s.running = false;
    s.work = 0;
    error.clear();
    if (!validate(p, error)) return false;
    try {
        s.seed = p.seed ? p.seed : static_cast<uint64_t>(
            std::chrono::high_resolution_clock::now().time_since_epoch().count());
        if (!s.seed) s.seed = 1;
        s.random.seed(s.seed);
        s.width = p.outputW == -1 ? 2048 : p.outputW;
        s.height = p.outputH == -1 ? 2048 : p.outputH;
        const int randomSymmetry = 3 + static_cast<int>(s.sample() * 5);
        s.symmetry = p.loomSymmetry == -1 ? randomSymmetry : p.loomSymmetry;
        // Draw all auto values even when overridden, so independent controls
        // retain the same underlying composition and palette randomness.
        s.turbulence = s.choose(p.loomTurbulence, .15 + .3 * s.sample());
        s.twist = s.choose(p.loomTwist, .12 + .32 * s.sample());
        s.spread = s.choose(p.loomSpread, .82 + .16 * s.sample());
        s.hue = s.choose(p.loomHue, 165 + 55 * s.sample());
        s.exposure = s.choose(p.loomExposure, 1);
        s.phase = s.sample() * 2 * PI;
        s.curlPhase = s.sample() * 2 * PI;
        const double rotation = .7 + s.twist * 1.1;
        s.rotationCos = std::cos(rotation);
        s.rotationSin = std::sin(rotation);
        s.scale = std::min(s.width, s.height) / 2.65;
        s.duration = p.duration == -1 ? 30 : p.duration;
        s.benchmark = p.benchmarkMode;
        s.poles.clear();
        for (int i = 0; i < s.symmetry; ++i) {
            const double angle = s.phase + 2 * PI * i / s.symmetry;
            const double outerAngle = angle + PI * .75 / s.symmetry;
            s.poles.push_back({{.43 * s.spread * std::cos(angle),
                                .43 * s.spread * std::sin(angle)}, 1});
            s.poles.push_back({{.78 * s.spread * std::cos(outerAngle),
                                .78 * s.spread * std::sin(outerAngle)}, -1});
        }
        for (auto& walk : s.walks) walk = Walk{};
        s.glow.clear();
        s.threads.clear();
        s.glow.reserve(STEPS_PER_TICK * 12);
        s.threads.reserve(STEPS_PER_TICK * 12);
        if (!s.canvas.create(static_cast<unsigned>(s.width), static_cast<unsigned>(s.height))) {
            error = "Could not create the Magnetic Loom render texture.";
            return false;
        }
        s.canvas.setSmooth(true);
        background(s);
        s.clock.restart();
        s.running = true;
        return true;
    } catch (const std::exception& exception) {
        error = std::string("Could not start Magnetic Loom: ") + exception.what();
        return false;
    }
}

bool loom_step() {
    auto& s = loom();
    if (!s.running) return false;
    if (!s.benchmark && s.clock.getElapsedTime().asSeconds() >= s.duration) {
        s.running = false;
        return false;
    }
    s.glow.clear();
    s.threads.clear();
    constexpr double stepLength = .0045;
    const float width = static_cast<float>(s.scale / 750.0);
    for (unsigned step = 0; step < STEPS_PER_TICK && s.work < WORK_TARGET; ++step) {
        auto& walk = s.walks[s.work % WALK_COUNT];
        if (walk.age >= STRAND_LENGTH) spawn(s, walk);
        const Vec before = walk.position;
        const Vec first = s.field(before) * (stepLength * walk.direction);
        const Vec delta = s.field(before + first * .5) * (stepLength * walk.direction);
        const Vec after = before + delta;
        ++s.work;
        ++walk.age;
        const double alignment = (first.x * delta.x + first.y * delta.y) / (stepLength * stepLength);
        // A normalized step can overshoot a field equilibrium. End that strand
        // instead of repeatedly bouncing across the sink and burning it white.
        if (!std::isfinite(after.x) || !std::isfinite(after.y) ||
            lengthSquared(after) > 2.8 || alignment < .2) {
            walk.age = STRAND_LENGTH;
            continue;
        }
        walk.position = after;
        const double taper = std::min({1.0, walk.age / 24.0, (STRAND_LENGTH - walk.age) / 48.0});
        const double edge = std::clamp((1.3 - std::sqrt(lengthSquared(after))) / .3, 0.0, 1.0);
        const double light = taper * edge * edge * (3 - 2 * edge) * walk.brightness * s.exposure;
        sf::Color color = walk.color;
        color.a = byte(light * 8);
        const auto a = s.pixel(before), b = s.pixel(after);
        ribbon(s.glow, a, b, width * 4.5f, color);
        color.a = byte(light * 90);
        ribbon(s.threads, a, b, width, color);
    }
    if (!s.glow.empty()) s.canvas.draw(s.glow.data(), s.glow.size(), sf::Triangles, sf::BlendAdd);
    if (!s.threads.empty()) s.canvas.draw(s.threads.data(), s.threads.size(), sf::Triangles, sf::BlendAdd);
    s.canvas.display();
    s.running = s.work < WORK_TARGET;
    return s.running;
}

const sf::Texture& loom_texture() { return loom().canvas.getTexture(); }
int loom_native_width() { return loom().width; }
int loom_native_height() { return loom().height; }
uint64_t loom_last_seed() { return loom().seed; }
GenPerformance loom_performance() { return {loom().work, WORK_TARGET, "field steps"}; }
