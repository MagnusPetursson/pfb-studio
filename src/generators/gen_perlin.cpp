// gen_perlin.cpp — wraps perlin.cpp in an anonymous namespace so its file-scope
// globals don't clash with the other generators when all are linked together.
// All of aural.hpp's definitions get internal linkage this way too.

#include "preinclude.hpp"
#include "generator.hpp"

namespace {
    // sfmlpp.h declares these as extern. Because the legacy source is included
    // inside this anonymous namespace, MSVC requires matching definitions in
    // the same translation unit even though these legacy helpers are unused.
    sf::RenderWindow window2;
    sf::Font font;

    // Rename perlin's main() so we can write our own init/step wrappers.
    #define main perlin_original_main
    // perlin.cpp defines WINDOW and NOISE at its top; WINDOW causes it to create
    // an sf::RenderWindow global but never calls window.create() (that's inside
    // the renamed main). We leave WINDOW defined so the #define doesn't conflict.
    #include "../legacy/perlin.cpp"
    #undef main
} // anonymous namespace

// ── helpers ─────────────────────────────────────────────────────────────────
// These functions live in the same TU and can therefore name the anon-ns symbols.

static bool     s_initialized = false;
static bool     s_done        = false;
static uint64_t s_lastSeed    = 0;

static void applyPerlinParams(const GenParams& p) {
    if (p.aspect == 1) {          // square
        WIDTH = HEIGHT = 2048;
        xlimit = ylimit = 3;
    } else if (p.aspect == 2) {   // wide
        WIDTH = 2048; HEIGHT = 1152;
        xlimit = 5.33; ylimit = 3;
    } else if (p.aspect == 3) {   // custom
        WIDTH  = std::max(64, p.customAspectW);
        HEIGHT = std::max(64, p.customAspectH);
        xlimit = ylimit = 3;
    }
    // aspect 0 = "original" → setup() already picked random aspect

    // flow preset / tree
    const std::string presetName = FLOW_PRESETS[p.flowPreset];
    if (presetName != "original") {
        struct Preset { int nodes, depth, variationChance; double coordScale, noiseScale; };
        auto getPreset = [](const std::string& n) -> Preset {
            if (n == "calmRibbons")   return {3, 2, 2,   100,  5};
            if (n == "broadCurrents") return {4, 3, 2,   10,   5};
            if (n == "fineFilaments") return {5, 4, 2,   500,  10};
            if (n == "knottedLace")   return {7, 5, 12,  100,  20};
            if (n == "turbulentGrain")return {7, 5, 35,  500, 100};
            if (n == "electricStatic")return {9, 6, 55, 1000, 100};
            if (n == "softGeometry")  return {5, 4, 8,    50,   5};
            return {5, 4, 2, 50, 10};
        };
        auto pr = getPreset(presetName);
        // Individual sliders override preset values if explicitly set
        int nodes = (p.fieldTreeNodes >= 0) ? p.fieldTreeNodes : pr.nodes;
        int depth = (p.fieldTreeDepth >= 0) ? p.fieldTreeDepth : pr.depth;
        int vchance = (p.variationChance >= 0) ? p.variationChance : pr.variationChance;
        tree1.clear(); nodes1.clear();
        createFieldTree2(nodes, depth, tree1, nodes1, vchance);
        coord_scale = !std::isnan(p.coordScale) ? p.coordScale : pr.coordScale;
        noise_scale = !std::isnan(p.noiseScale) ? p.noiseScale : pr.noiseScale;
    } else {
        // "original" preset: apply individual overrides only when explicitly set
        if (p.fieldTreeNodes >= 0 || p.fieldTreeDepth >= 0 || p.variationChance >= 0) {
            int nodes   = (p.fieldTreeNodes  >= 0) ? p.fieldTreeNodes  : 5;
            int depth   = (p.fieldTreeDepth  >= 0) ? p.fieldTreeDepth  : 4;
            int vchance = (p.variationChance >= 0) ? p.variationChance : 2;
            tree1.clear(); nodes1.clear();
            createFieldTree2(nodes, depth, tree1, nodes1, vchance);
        }
        if (!std::isnan(p.coordScale)) coord_scale = p.coordScale;
        if (!std::isnan(p.noiseScale)) noise_scale = p.noiseScale;
    }

    // individual overrides (skip if NaN → generator keeps its own random value)
    if (!std::isnan(p.smoothing))   smoothing    = p.smoothing;
    if (!std::isnan(p.flowSpeed))   vector_scale = p.flowSpeed;
    if (!std::isnan(p.fieldWeight)) weight       = p.fieldWeight;
    if (!std::isnan(p.hue))         hue          = p.hue;
    if (!std::isnan(p.contrast))    contrast     = p.contrast;
    if (p.coloredSet) is_colored = p.colored;

    if (!std::isnan(p.density)) {
        step = 0.035 / p.density;
        points.clear();
        const auto estimatedPointCount = static_cast<size_t>(
            (2.0 * xlimit / step + 2.0) * (2.0 * ylimit / step + 2.0));
        points.reserve(estimatedPointCount);
        for (double i = -xlimit; i <= xlimit; i += step)
            for (double j = -ylimit; j <= ylimit; j += step)
                points.push_back(particle(i + 0.003*rdnormal(0,1),
                                           j + 0.003*rdnormal(0,1),
                                           sf::Color(0,0,0,30)));
    }

    if (p.duration > 0) timeLimit = p.duration;
}

// ── public interface ─────────────────────────────────────────────────────────

bool perlin_start(const GenParams& p, std::string& error) {
    s_done = false;
    error.clear();

    timerClock.restart();

    // Determine seed
    uint64_t useSeed = p.seed ? p.seed : seedgen();
    seedgen(useSeed);

    // Clear mutable state so restarts are clean
    points.clear();
    tree1.clear();
    nodes1.clear();

    setup();               // randomises layout, fills points, builds field tree
    applyPerlinParams(p);  // override with user params after setup()

    // Rebuild the render texture at current WIDTH/HEIGHT
    renderTexture.create(WIDTH, HEIGHT);
    pn.SetNoiseType(FastNoise::PerlinFractal);
    pn.SetFractalOctaves(octaves);
    pn.SetSeed((int)useSeed);

    // Background painting (mirrors original main())
    if (is_colored) {
        pal = randomPalette(4, 50, rd(0.5, 0.9), rd(0.2, 0.6), hue, 2);
        int brightness = (int)mathmap(contrast, 0, 1, 30, 220);
        bg1 = sf::Color(
            (sf::Uint8)constrain(rdnormal(brightness, brightness/20.0), 0, 255),
            (sf::Uint8)constrain(rdnormal(brightness, brightness/20.0), 0, 255),
            (sf::Uint8)constrain(rdnormal(brightness, brightness/20.0), 0, 255));
        bg2 = sf::Color(
            (sf::Uint8)rdnormal(brightness/1.2, brightness/50.0),
            (sf::Uint8)rdnormal(brightness/1.2, brightness/50.0),
            (sf::Uint8)rdnormal(brightness/1.2, brightness/50.0));
    } else {
        bg1 = sf::Color((sf::Uint8)rdnormal(220,1),(sf::Uint8)rdnormal(220,1),(sf::Uint8)rdnormal(220,1));
        bg2 = sf::Color((sf::Uint8)rdnormal(180,1),(sf::Uint8)rdnormal(180,1),(sf::Uint8)rdnormal(180,1));
    }

    renderTexture.clear(bg1);
    double invert_hue = (hue + 180 > 360 ? hue - 180 : hue + 180);
    sf::Vertex rectangle[] = {
        sf::Vertex(sf::Vector2f(0, 0),
            randomPalette(1, (int)rd(30,80), 0.98, rd(0.2,0.4), rdnormal(invert_hue,10))[0]),
        sf::Vertex(sf::Vector2f((float)WIDTH, 0),
            randomPalette(1, (int)rd(30,80), 0.98, rd(0.2,0.4), rdnormal(invert_hue,10))[0]),
        sf::Vertex(sf::Vector2f((float)WIDTH, (float)HEIGHT),
            randomPalette(1, (int)rd(30,80), 0.98, rd(0.2,0.4), rdnormal(invert_hue,10))[0]),
        sf::Vertex(sf::Vector2f(0, (float)HEIGHT),
            randomPalette(1, (int)rd(30,80), 0.98, rd(0.2,0.4), rdnormal(invert_hue,10))[0])
    };
    renderTexture.draw(rectangle, 4, sf::Quads);
    renderTexture.display();

    // Noise grain on background. Generate the final pixel colors on the CPU,
    // upload once, then draw the completed image in a single submission rather
    // than issuing one draw call for every pixel.
    auto image = renderTexture.getTexture().copyToImage();
    for (int i = 1; i < HEIGHT; i++) {
        for (int j = 1; j < WIDTH; j++) {
            auto pc = image.getPixel(j, i);
            pc = sf::Color(
                (sf::Uint8)constrain(rdnormal(pc.r,2), pc.r/2.0, std::min(255, pc.r*2)),
                (sf::Uint8)constrain(rdnormal(pc.g,2), pc.g/2.0, std::min(255, pc.g*2)),
                (sf::Uint8)constrain(rdnormal(pc.b,2), pc.b/2.0, std::min(255, pc.b*2)));
            image.setPixel(j, i, pc);
        }
    }
    sf::Texture grainTexture;
    if (!grainTexture.loadFromImage(image)) {
        error = "Could not upload the Perlin background grain texture.";
        return false;
    }
    renderTexture.draw(sf::Sprite(grainTexture));
    renderTexture.display();

    timerClock.restart(); // restart after setup so timeLimit is measured from first step
    s_lastSeed    = useSeed;
    s_initialized = true;
    return true;
}

bool perlin_step() {
    if (!s_initialized || s_done) return false;
    if (timerClock.getElapsedTime().asSeconds() >= (float)timeLimit) {
        s_done = true;
        return false;
    }
    sf::Vertex point;
    point.color    = sf::Color(0, 0, 0, 0);
    point.position = sf::Vector2f((float)rd(0, WIDTH), (float)rd(0, HEIGHT));
    renderTexture.draw(&point, 1, sf::Points);
    draw();
    renderTexture.display();
    return true;
}

const sf::Texture& perlin_texture() {
    return renderTexture.getTexture();
}

int perlin_native_width()  { return WIDTH;  }
int perlin_native_height() { return HEIGHT; }
uint64_t perlin_last_seed() { return s_lastSeed; }
