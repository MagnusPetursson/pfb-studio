#pragma once
#include <SFML/Graphics.hpp>
#include <string>
#include <cstdint>
#include <cmath>
#include <limits>

// Aspect options for perlin
inline constexpr const char* ASPECT_OPTIONS[] = { "original", "square", "wide", "custom" };
inline constexpr const char* FLOW_PRESETS[]   = { "original", "calmRibbons", "broadCurrents",
                                         "fineFilaments", "knottedLace", "turbulentGrain",
                                         "electricStatic", "softGeometry" };
static const int ASPECT_COUNT     = 4;
static const int FLOW_PRESET_COUNT = 8;

struct GenPerformance {
    uint64_t workUnits = 0;
    uint64_t benchmarkTarget = 0;
    const char* unitLabel = "work units";
};

struct GenParams {
    // Sentinel: NaN for doubles means "let the generator randomise this param".
    //           -1 for ints means the same.
    static constexpr double R = std::numeric_limits<double>::quiet_NaN();

    // ---- shared ----
    uint64_t seed     = 0;   // 0 = let generator pick
    double   duration = -1;  // -1 = use generator default
    int      outputW  = -1;  // -1 = use generator default
    int      outputH  = -1;
    bool     benchmarkMode = false; // fixed-work profiling run; ignores duration

    // ---- perlin ----
    int    aspect          = 0;    // index into ASPECT_OPTIONS (0 = "original random")
    int    customAspectW   = 1920;
    int    customAspectH   = 1080;
    int    flowPreset      = 0;    // index into FLOW_PRESETS (0 = "original random")
    double density         = R;
    double smoothing       = R;
    double flowSpeed       = R;
    double fieldWeight     = R;
    double hue             = R;
    bool   colored         = true;
    bool   coloredSet      = false;
    double contrast        = R;
    int    fieldTreeNodes  = -1;   // -1 = random
    int    fieldTreeDepth  = -1;
    int    variationChance = -1;
    double coordScale      = R;
    double noiseScale      = R;

    // ---- fractal ----
    double preprocessTime  = R;
    bool   fractalBlur     = true;
    bool   fractalBlurSet  = false;
    double fractalHue      = R;

    // ---- circle (organic growth) ----
    double colonyScale     = R;
    double proximityScale  = R;
    double noiseScaleCircle= R;
    double coordScaleCircle= R;
    double timeStepScale   = R;

    // ---- fujii attractor ----
    double velocity        = R;
    double p               = R;
    double q               = R;
    double coefficientScale= R;
    double frequencyScale  = R;
    double colorLimit      = R;

    // ---- galaxies ----
    double attractorScale  = R;
    double colorLimitGal   = R;
};

// Each generator exposes these functions (defined in their respective .cpp):
// bool perlin_start(const GenParams& p, const std::string& rootDir, std::string& error);
// bool perlin_step  ();
// const sf::Texture& perlin_texture ();
// int  perlin_native_width  ();
// int  perlin_native_height ();
// ... same pattern for fractal_, circle_, fujii_, galaxies_

bool perlin_start  (const GenParams& p, std::string& error);
bool perlin_step   ();
const sf::Texture& perlin_texture   ();
int      perlin_native_width  ();
int      perlin_native_height ();
uint64_t perlin_last_seed     ();
GenPerformance perlin_performance();

bool fractal_start (const GenParams& p, std::string& error);
bool fractal_step  ();
const sf::Texture& fractal_texture  ();
int      fractal_native_width ();
int      fractal_native_height();
uint64_t fractal_last_seed    ();
GenPerformance fractal_performance();

bool circle_start  (const GenParams& p, std::string& error);
bool circle_step   ();
const sf::Texture& circle_texture   ();
int      circle_native_width  ();
int      circle_native_height ();
uint64_t circle_last_seed     ();
GenPerformance circle_performance();

bool fujii_start   (const GenParams& p, std::string& error);
bool fujii_step    ();
const sf::Texture& fujii_texture    ();
int      fujii_native_width   ();
int      fujii_native_height  ();
uint64_t fujii_last_seed      ();
GenPerformance fujii_performance();

bool galaxies_start(const GenParams& p, std::string& error);
bool galaxies_step ();
const sf::Texture& galaxies_texture ();
int      galaxies_native_width ();
int      galaxies_native_height();
uint64_t galaxies_last_seed    ();
GenPerformance galaxies_performance();
