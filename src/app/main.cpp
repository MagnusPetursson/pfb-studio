// launcher.cpp - PFB Studio native launcher
//
// Art-first SFML viewport with a Dear ImGui inspector. Generator code remains
// isolated behind the wrapper functions declared in generator.hpp.

#include "generator.hpp"
#include "app_support.hpp"
#include "platform.hpp"
#include "version.hpp"

#include "imgui.h"
#include "imgui-SFML.h"

#include <SFML/Graphics.hpp>
#include <SFML/System.hpp>
#include <SFML/Window.hpp>

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <functional>
#include <fstream>
#include <iostream>
#include <limits>
#include <string>
#include <system_error>
#include <utility>

enum GenId { GEN_PERLIN = 0, GEN_FRACTAL, GEN_CIRCLE, GEN_FUJII, GEN_GALAXIES, GEN_COUNT };
enum class RunState { Idle, Starting, Running, Complete, Canceled, Error };

static const char* GEN_SHORT[] = { "Perlin", "Fractal", "Circle", "Fujii", "Galaxy" };
static const char* GEN_LABELS[] = {
    "Noise Flowfield",
    "Fractal Flame",
    "Organic Growth",
    "Fujii Attractor",
    "Galaxies"
};
static const char* GEN_SLUGS[] = { "perlin", "fractal", "circle", "fujii", "galaxy" };

static const char* ASPECT_LABELS[] = {
    "Original random", "Square", "Wide", "Custom"
};
static const char* FLOW_LABELS[] = {
    "Original random", "Calm ribbons", "Broad currents", "Fine filaments",
    "Knotted lace", "Turbulent grain", "Electric static", "Soft geometry"
};

struct UiDefaults {
    int width;
    int height;
    float duration;
};

static const UiDefaults DEFAULTS[GEN_COUNT] = {
    {2048, 2048, 22.f},
    {2000, 2000, 40.f},
    {1800, 1800, 60.f},
    {2048, 2048, 30.f},
    {2048, 2048, 30.f}
};

static sf::RenderWindow* gWin = nullptr;
static bool gFullscreen = false;
static bool gImguiReady = false;
static int gWinW = 1440;
static int gWinH = 960;

static GenId activeGen = GEN_PERLIN;
static int runningGen = -1;
static GenParams params[GEN_COUNT];
static RunState runStates[GEN_COUNT] = {
    RunState::Idle, RunState::Idle, RunState::Idle, RunState::Idle, RunState::Idle
};
static float elapsedByGen[GEN_COUNT] = {};
static float setupElapsedByGen[GEN_COUNT] = {};
static uint64_t lastSeeds[GEN_COUNT] = {};
static bool hasPreview[GEN_COUNT] = {};
static std::string errors[GEN_COUNT];
static std::string saveStatus;
static bool saveStatusIsError = false;
static bool showLiveStats = true;
static sf::Clock genClock;

static const sf::Color COL_BG{7, 8, 10};
static const sf::Color COL_ACCENT{226, 92, 78};

static bool anyRunning() {
    return runningGen >= 0 && runningGen < GEN_COUNT && runStates[runningGen] == RunState::Running;
}

static bool isAuto(double value) {
    return std::isnan(value);
}

static void resetParams(GenId id) {
    params[id] = GenParams{};
}

static const char* stateLabel(RunState state) {
    switch (state) {
        case RunState::Starting: return "Starting";
        case RunState::Running:  return "Rendering";
        case RunState::Complete: return "Complete";
        case RunState::Canceled: return "Canceled";
        case RunState::Error:    return "Error";
        case RunState::Idle:
        default:                 return "Idle";
    }
}

static ImVec4 stateColor(RunState state) {
    switch (state) {
        case RunState::Running:
        case RunState::Starting: return ImVec4(0.38f, 0.78f, 0.52f, 1.f);
        case RunState::Complete: return ImVec4(0.94f, 0.72f, 0.30f, 1.f);
        case RunState::Canceled: return ImVec4(0.58f, 0.62f, 0.70f, 1.f);
        case RunState::Error:    return ImVec4(0.88f, 0.39f, 0.39f, 1.f);
        case RunState::Idle:
        default:                 return ImVec4(0.58f, 0.62f, 0.70f, 1.f);
    }
}

static uint64_t getLastSeed(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return perlin_last_seed();
        case GEN_FRACTAL:  return fractal_last_seed();
        case GEN_CIRCLE:   return circle_last_seed();
        case GEN_FUJII:    return fujii_last_seed();
        case GEN_GALAXIES: return galaxies_last_seed();
        default: return 0;
    }
}

static GenPerformance performanceGen(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return perlin_performance();
        case GEN_FRACTAL:  return fractal_performance();
        case GEN_CIRCLE:   return circle_performance();
        case GEN_FUJII:    return fujii_performance();
        case GEN_GALAXIES: return galaxies_performance();
        default: return {};
    }
}

static void formatMetric(double value, char* buffer, std::size_t size) {
    if (value >= 1000000000.0)
        std::snprintf(buffer, size, "%.2fB", value / 1000000000.0);
    else if (value >= 1000000.0)
        std::snprintf(buffer, size, "%.2fM", value / 1000000.0);
    else if (value >= 1000.0)
        std::snprintf(buffer, size, "%.2fk", value / 1000.0);
    else
        std::snprintf(buffer, size, "%.0f", value);
}

static float runProgress(GenId id) {
    if (params[id].benchmarkMode) {
        const GenPerformance perf = performanceGen(id);
        if (perf.benchmarkTarget == 0) return 0.f;
        return std::clamp(static_cast<float>(
            static_cast<double>(perf.workUnits) / static_cast<double>(perf.benchmarkTarget)), 0.f, 1.f);
    }
    const float target = params[id].duration > 0
        ? static_cast<float>(params[id].duration)
        : DEFAULTS[id].duration;
    return std::clamp(elapsedByGen[id] / std::max(1.f, target), 0.f, 1.f);
}

static bool stepGen(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return perlin_step();
        case GEN_FRACTAL:  return fractal_step();
        case GEN_CIRCLE:   return circle_step();
        case GEN_FUJII:    return fujii_step();
        case GEN_GALAXIES: return galaxies_step();
        default: return false;
    }
}

static const sf::Texture* textureGen(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return &perlin_texture();
        case GEN_FRACTAL:  return &fractal_texture();
        case GEN_CIRCLE:   return &circle_texture();
        case GEN_FUJII:    return &fujii_texture();
        case GEN_GALAXIES: return &galaxies_texture();
        default: return nullptr;
    }
}

static int nativeW(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return perlin_native_width();
        case GEN_FRACTAL:  return fractal_native_width();
        case GEN_CIRCLE:   return circle_native_width();
        case GEN_FUJII:    return fujii_native_width();
        case GEN_GALAXIES: return galaxies_native_width();
        default: return 2048;
    }
}

static int nativeH(GenId id) {
    switch (id) {
        case GEN_PERLIN:   return perlin_native_height();
        case GEN_FRACTAL:  return fractal_native_height();
        case GEN_CIRCLE:   return circle_native_height();
        case GEN_FUJII:    return fujii_native_height();
        case GEN_GALAXIES: return galaxies_native_height();
        default: return 2048;
    }
}

static std::filesystem::path defaultSavePath(GenId id) {
    return pfb::defaultImagePath(GEN_SLUGS[id], lastSeeds[id]);
}

static bool canSaveActiveImage() {
    return !anyRunning() && hasPreview[activeGen] && runStates[activeGen] == RunState::Complete;
}

static void setSaveStatus(std::string status, bool isError = false) {
    saveStatus = std::move(status);
    saveStatusIsError = isError;
}

static void saveActiveImage() {
    if (!canSaveActiveImage()) {
        setSaveStatus("Generate a complete image before saving.", true);
        return;
    }

    const sf::Texture* texture = textureGen(activeGen);
    if (!texture || texture->getSize().x == 0 || texture->getSize().y == 0) {
        setSaveStatus("No image texture is available to save.", true);
        return;
    }

    const pfb::SaveDialogResult dialog = pfb::chooseImageSavePath(defaultSavePath(activeGen));
    if (dialog.status == pfb::DialogStatus::Canceled) {
        setSaveStatus("Save canceled.");
        return;
    }
    if (dialog.status == pfb::DialogStatus::Error) {
        setSaveStatus(dialog.error.empty() ? "Could not choose a save path." : dialog.error, true);
        return;
    }

    sf::Image image = texture->copyToImage();
    const std::filesystem::path chosenPath = pfb::normalizeImagePath(dialog.path);
    std::string error;
    if (pfb::writeImage(image, chosenPath, error)) {
        setSaveStatus("Saved: " + chosenPath.string());
    } else {
        setSaveStatus(error.empty() ? "Could not save: " + chosenPath.string() : error, true);
    }
}

static bool startGen(GenId id, bool replayLast) {
    if (anyRunning()) return false;
    if (replayLast && params[id].seed == 0 && lastSeeds[id] == 0) return false;

    GenParams& p = params[id];
    uint64_t visibleSeed = p.seed;
    if (replayLast && p.seed == 0) p.seed = lastSeeds[id];

    activeGen = id;
    runningGen = id;
    runStates[id] = RunState::Starting;
    elapsedByGen[id] = 0.f;
    setupElapsedByGen[id] = 0.f;
    errors[id].clear();
    saveStatus.clear();
    saveStatusIsError = false;
    genClock.restart();

    bool ok = false;
    std::string error;
    switch (id) {
        case GEN_PERLIN:   ok = perlin_start(p, error); break;
        case GEN_FRACTAL:  ok = fractal_start(p, error); break;
        case GEN_CIRCLE:   ok = circle_start(p, error); break;
        case GEN_FUJII:    ok = fujii_start(p, error); break;
        case GEN_GALAXIES: ok = galaxies_start(p, error); break;
        default: break;
    }

    setupElapsedByGen[id] = genClock.getElapsedTime().asSeconds();
    p.seed = visibleSeed;
    if (!ok) {
        runStates[id] = RunState::Error;
        errors[id] = error.empty() ? "Generator failed to start." : error;
        runningGen = -1;
        return false;
    }

    lastSeeds[id] = getLastSeed(id);
    hasPreview[id] = true;
    runStates[id] = RunState::Running;
    genClock.restart(); // profile/render duration starts after synchronous setup
    return true;
}

static void stopGen() {
    if (!anyRunning()) return;
    elapsedByGen[runningGen] = genClock.getElapsedTime().asSeconds();
    runStates[runningGen] = RunState::Canceled;
    runningGen = -1;
}

static void stepRunningGen() {
    if (!anyRunning()) return;
    GenId id = static_cast<GenId>(runningGen);
    bool keepGoing = stepGen(id);
    elapsedByGen[id] = genClock.getElapsedTime().asSeconds();
    if (!keepGoing) {
        runStates[id] = RunState::Complete;
        runningGen = -1;
    }
}

static void alignAutoButton(float buttonWidth = 54.f) {
    float x = ImGui::GetCursorPosX() + ImGui::GetContentRegionAvail().x - buttonWidth;
    if (x > ImGui::GetCursorPosX()) ImGui::SameLine(x);
}

static bool autoButton(bool active) {
    if (active) {
        ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.88f, 0.36f, 0.31f, 0.92f));
        ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.95f, 0.44f, 0.38f, 1.f));
        ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.78f, 0.28f, 0.24f, 1.f));
    }
    bool clicked = ImGui::SmallButton("Auto");
    if (active) ImGui::PopStyleColor(3);
    return clicked;
}

static void paramHeader(const char* label, bool autoState, bool* resetAuto) {
    ImGui::TextUnformatted(label);
    alignAutoButton();
    if (autoButton(autoState) && resetAuto) *resetAuto = true;
}

static void markItemAutoAlpha(bool autoState) {
    if (autoState) ImGui::PushStyleVar(ImGuiStyleVar_Alpha, ImGui::GetStyle().Alpha * 0.70f);
}

static void popItemAutoAlpha(bool autoState) {
    if (autoState) ImGui::PopStyleVar();
}

static bool drawDoubleParam(const char* id, const char* label, double& target,
                            float fallback, float mn, float mx, const char* fmt,
                            bool hue = false, ImGuiSliderFlags flags = 0) {
    ImGui::PushID(id);
    bool reset = false;
    bool autoState = isAuto(target);
    paramHeader(label, autoState, &reset);
    if (reset) {
        target = GenParams::R;
        ImGui::PopID();
        return true;
    }

    float v = autoState ? fallback : static_cast<float>(target);
    bool changed = false;

    markItemAutoAlpha(autoState);
    if (hue) {
        ImVec4 color = ImColor::HSV(std::clamp(v, 0.f, 360.f) / 360.f, 0.78f, 0.95f);
        ImGui::ColorButton("##swatch", color, ImGuiColorEditFlags_NoTooltip, ImVec2(24, 24));
        ImGui::SameLine();
    }
    float inputW = 82.f;
    float sliderW = ImGui::GetContentRegionAvail().x - inputW - 8.f;
    ImGui::SetNextItemWidth(std::max(90.f, sliderW));
    changed |= ImGui::SliderFloat("##slider", &v, mn, mx, fmt, flags);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(inputW);
    changed |= ImGui::InputFloat("##value", &v, 0.f, 0.f, fmt);
    popItemAutoAlpha(autoState);

    if (changed) target = std::clamp(v, mn, mx);
    ImGui::PopID();
    return changed || reset;
}

static bool drawIntParam(const char* id, const char* label, int& target,
                         int fallback, int mn, int mx) {
    ImGui::PushID(id);
    bool reset = false;
    bool autoState = target < 0;
    paramHeader(label, autoState, &reset);
    if (reset) {
        target = -1;
        ImGui::PopID();
        return true;
    }

    int v = autoState ? fallback : target;
    bool changed = false;
    markItemAutoAlpha(autoState);
    float inputW = 82.f;
    float sliderW = ImGui::GetContentRegionAvail().x - inputW - 8.f;
    ImGui::SetNextItemWidth(std::max(90.f, sliderW));
    changed |= ImGui::SliderInt("##slider", &v, mn, mx);
    ImGui::SameLine();
    ImGui::SetNextItemWidth(inputW);
    changed |= ImGui::InputInt("##value", &v, 1, 10);
    popItemAutoAlpha(autoState);

    if (changed) target = std::clamp(v, mn, mx);
    ImGui::PopID();
    return changed || reset;
}

static bool drawDurationParam(GenId id) {
    GenParams& p = params[id];
    ImGui::PushID("duration");
    bool reset = false;
    bool autoState = p.duration <= 0;
    paramHeader("Duration", autoState, &reset);
    if (reset) {
        p.duration = -1;
        ImGui::PopID();
        return true;
    }

    float v = autoState ? DEFAULTS[id].duration : static_cast<float>(p.duration);
    bool changed = false;
    markItemAutoAlpha(autoState);
    float inputW = 82.f;
    float sliderW = ImGui::GetContentRegionAvail().x - inputW - 8.f;
    ImGui::SetNextItemWidth(std::max(90.f, sliderW));
    changed |= ImGui::SliderFloat("##slider", &v, 1.f, 300.f, "%.0f s");
    ImGui::SameLine();
    ImGui::SetNextItemWidth(inputW);
    changed |= ImGui::InputFloat("##value", &v, 0.f, 0.f, "%.0f");
    popItemAutoAlpha(autoState);

    if (changed) p.duration = std::clamp(v, 1.f, 300.f);
    ImGui::PopID();
    return changed || reset;
}

static void drawSeedWidget(GenId id) {
    GenParams& p = params[id];
    ImGui::PushID("seed");
    bool isAutoSeed = p.seed == 0;
    ImGui::TextUnformatted("Seed");
    alignAutoButton();
    if (autoButton(isAutoSeed)) p.seed = 0;

    uint64_t editSeed = isAutoSeed ? lastSeeds[id] : p.seed;
    markItemAutoAlpha(isAutoSeed);
    ImGui::SetNextItemWidth(-1);
    if (ImGui::InputScalar("##seed", ImGuiDataType_U64, &editSeed)) {
        p.seed = editSeed;
    }
    popItemAutoAlpha(isAutoSeed);

    if (lastSeeds[id]) {
        ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f), "Last seed: %llu",
                           static_cast<unsigned long long>(lastSeeds[id]));
    } else {
        ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f), "Last seed: none");
    }
    ImGui::PopID();
}

static void drawBoolCombo(const char* id, const char* label, bool& value, bool& setFlag,
                          bool fallback, const char* yes, const char* no) {
    ImGui::PushID(id);
    bool reset = false;
    bool autoState = !setFlag;
    paramHeader(label, autoState, &reset);
    if (reset) setFlag = false;

    bool shownValue = setFlag ? value : fallback;
    int selected = shownValue ? 0 : 1;
    const char* labels[] = { yes, no };
    markItemAutoAlpha(autoState);
    ImGui::SetNextItemWidth(-1);
    if (ImGui::Combo("##combo", &selected, labels, 2)) {
        value = selected == 0;
        setFlag = true;
    }
    popItemAutoAlpha(autoState);
    ImGui::PopID();
}

static void drawBoolCheckbox(const char* id, const char* label, bool& value, bool& setFlag,
                             bool fallback) {
    ImGui::PushID(id);
    bool reset = false;
    bool autoState = !setFlag;
    paramHeader(label, autoState, &reset);
    if (reset) setFlag = false;

    bool shownValue = setFlag ? value : fallback;
    markItemAutoAlpha(autoState);
    if (ImGui::Checkbox("##check", &shownValue)) {
        value = shownValue;
        setFlag = true;
    }
    popItemAutoAlpha(autoState);
    ImGui::SameLine();
    ImGui::TextUnformatted(shownValue ? "Enabled" : "Disabled");
    ImGui::PopID();
}

static void drawPinnedInt(const char* id, const char* label, int& value, int mn, int mx) {
    ImGui::PushID(id);
    ImGui::TextUnformatted(label);
    ImGui::SetNextItemWidth(-1);
    value = std::clamp(value, mn, mx);
    ImGui::SliderInt("##value", &value, mn, mx);
    ImGui::PopID();
}

static void drawOutputSize(GenId id, int maxValue) {
    GenParams& p = params[id];
    drawIntParam("outputW", "Output width", p.outputW, DEFAULTS[id].width, 512, maxValue);
    drawIntParam("outputH", "Output height", p.outputH, DEFAULTS[id].height, 512, maxValue);
}

static void section(const char* label) {
    ImGui::Spacing();
    ImGui::SeparatorText(label);
}

static void drawParams(GenId id) {
    GenParams& p = params[id];

    section("Timing");
    drawDurationParam(id);

    if (id == GEN_PERLIN) {
        section("Canvas");
        ImGui::SetNextItemWidth(-1);
        ImGui::Combo("Aspect ratio", &p.aspect, ASPECT_LABELS, ASPECT_COUNT);
        if (p.aspect == 3) {
            drawPinnedInt("customW", "Width", p.customAspectW, 512, 4096);
            drawPinnedInt("customH", "Height", p.customAspectH, 512, 4096);
        }

        section("Flow");
        ImGui::SetNextItemWidth(-1);
        ImGui::Combo("Flow structure", &p.flowPreset, FLOW_LABELS, FLOW_PRESET_COUNT);
        drawDoubleParam("density", "Density", p.density, 1.f, 0.25f, 4.f, "%.2f");
        drawDoubleParam("smoothing", "Smoothing", p.smoothing, 0.5f, 0.f, 0.99f, "%.2f");
        drawDoubleParam("flowSpeed", "Flow speed", p.flowSpeed, 0.001f, 0.0001f, 0.01f, "%.4f");
        drawDoubleParam("fieldWeight", "Field weight", p.fieldWeight, 1.f, 0.1f, 5.f, "%.2f");

        section("Color");
        drawDoubleParam("hue", "Hue", p.hue, 180.f, 0.f, 360.f, "%.0f", true);
        drawBoolCombo("colorMode", "Color mode", p.colored, p.coloredSet, true, "Color", "Monochrome");
        drawDoubleParam("contrast", "Contrast", p.contrast, 0.f, 0.f, 1.f, "%.2f");

        if (ImGui::CollapsingHeader("Advanced field", ImGuiTreeNodeFlags_DefaultOpen)) {
            drawIntParam("fieldTreeNodes", "Field nodes", p.fieldTreeNodes, 5, 1, 12);
            drawIntParam("fieldTreeDepth", "Field depth", p.fieldTreeDepth, 4, 1, 8);
            drawIntParam("variationChance", "Variation chance", p.variationChance, 2, 0, 100);
            drawDoubleParam("coordScale", "Coordinate scale", p.coordScale, 50.f, 1.f, 2000.f, "%.0f");
            drawDoubleParam("noiseScale", "Noise scale", p.noiseScale, 10.f, 1.f, 250.f, "%.0f");
        }
    } else if (id == GEN_FRACTAL) {
        section("Color");
        drawDoubleParam("fractalHue", "Hue", p.fractalHue, 180.f, 0.f, 360.f, "%.0f", true);
        drawBoolCheckbox("blur", "Bloom pass", p.fractalBlur, p.fractalBlurSet, true);

        section("Flame");
        drawDoubleParam("preprocess", "Preprocess", p.preprocessTime, 8.f, 1.f, 60.f, "%.0f s");

        if (ImGui::CollapsingHeader("Output")) drawOutputSize(id, 2000);
    } else if (id == GEN_CIRCLE) {
        section("Growth");
        drawDoubleParam("colonyScale", "Colony scale", p.colonyScale, 1.f, 0.2f, 3.f, "%.2f");
        drawDoubleParam("proximityScale", "Proximity", p.proximityScale, 1.f, 0.1f, 5.f, "%.2f");

        section("Noise");
        drawDoubleParam("noiseScaleCircle", "Noise scale", p.noiseScaleCircle, 1.f, 0.1f, 5.f, "%.2f");
        drawDoubleParam("coordScaleCircle", "Coordinate scale", p.coordScaleCircle, 1.f, 0.1f, 5.f, "%.2f");
        drawDoubleParam("timeStepScale", "Time step", p.timeStepScale, 1.f, 0.1f, 5.f, "%.2f");

        if (ImGui::CollapsingHeader("Output")) drawOutputSize(id, 4096);
    } else if (id == GEN_FUJII) {
        section("Attractor");
        drawDoubleParam("velocity", "Velocity", p.velocity, 0.05f, 0.0001f, 2.f, "%.4f");
        drawDoubleParam("p", "P exponent", p.p, 2.f, 0.f, 10.f, "%.2f");
        drawDoubleParam("q", "Q exponent", p.q, 2.f, 0.f, 10.f, "%.2f");

        section("Scale");
        drawDoubleParam("coefficientScale", "Coefficient scale", p.coefficientScale, 1.f, 0.1f, 5.f, "%.2f");
        drawDoubleParam("frequencyScale", "Frequency scale", p.frequencyScale, 1.f, 0.1f, 5.f, "%.2f");
        drawDoubleParam("colorLimit", "Color limit", p.colorLimit, 1.f, 0.1f, 10.f, "%.2f");

        if (ImGui::CollapsingHeader("Output")) drawOutputSize(id, 4096);
    } else if (id == GEN_GALAXIES) {
        section("Simulation");
        drawDoubleParam("attractorScale", "Attractor scale", p.attractorScale, 1.f, 0.2f, 3.f, "%.2f");

        section("Color");
        drawDoubleParam("colorLimitGal", "Color limit", p.colorLimitGal, 1.f, 0.1f, 10.f, "%.2f");

        if (ImGui::CollapsingHeader("Output")) drawOutputSize(id, 4096);
    }
}

static void configureImGuiStyle() {
    ImGuiStyle& style = ImGui::GetStyle();
    style.WindowRounding = 8.f;
    style.ChildRounding = 6.f;
    style.FrameRounding = 5.f;
    style.PopupRounding = 6.f;
    style.ScrollbarRounding = 6.f;
    style.GrabRounding = 5.f;
    style.TabRounding = 5.f;
    style.WindowBorderSize = 1.f;
    style.FrameBorderSize = 1.f;
    style.WindowPadding = ImVec2(16.f, 16.f);
    style.FramePadding = ImVec2(9.f, 6.f);
    style.ItemSpacing = ImVec2(9.f, 8.f);
    style.ItemInnerSpacing = ImVec2(8.f, 6.f);
    style.ScrollbarSize = 12.f;

    ImVec4* c = style.Colors;
    c[ImGuiCol_Text] = ImVec4(0.94f, 0.95f, 0.97f, 1.f);
    c[ImGuiCol_TextDisabled] = ImVec4(0.48f, 0.51f, 0.57f, 1.f);
    c[ImGuiCol_WindowBg] = ImVec4(0.075f, 0.075f, 0.082f, 0.94f);
    c[ImGuiCol_ChildBg] = ImVec4(0.095f, 0.095f, 0.105f, 0.62f);
    c[ImGuiCol_PopupBg] = ImVec4(0.09f, 0.09f, 0.10f, 0.98f);
    c[ImGuiCol_Border] = ImVec4(0.24f, 0.24f, 0.27f, 0.72f);
    c[ImGuiCol_FrameBg] = ImVec4(0.14f, 0.14f, 0.16f, 0.92f);
    c[ImGuiCol_FrameBgHovered] = ImVec4(0.22f, 0.20f, 0.19f, 0.96f);
    c[ImGuiCol_FrameBgActive] = ImVec4(0.29f, 0.24f, 0.22f, 1.f);
    c[ImGuiCol_TitleBg] = c[ImGuiCol_WindowBg];
    c[ImGuiCol_TitleBgActive] = c[ImGuiCol_WindowBg];
    c[ImGuiCol_CheckMark] = ImVec4(0.94f, 0.72f, 0.30f, 1.f);
    c[ImGuiCol_SliderGrab] = ImVec4(0.88f, 0.36f, 0.31f, 1.f);
    c[ImGuiCol_SliderGrabActive] = ImVec4(0.94f, 0.72f, 0.30f, 1.f);
    c[ImGuiCol_Button] = ImVec4(0.18f, 0.17f, 0.17f, 0.95f);
    c[ImGuiCol_ButtonHovered] = ImVec4(0.34f, 0.25f, 0.23f, 1.f);
    c[ImGuiCol_ButtonActive] = ImVec4(0.74f, 0.28f, 0.24f, 1.f);
    c[ImGuiCol_Header] = ImVec4(0.24f, 0.20f, 0.19f, 0.86f);
    c[ImGuiCol_HeaderHovered] = ImVec4(0.34f, 0.25f, 0.23f, 0.96f);
    c[ImGuiCol_HeaderActive] = ImVec4(0.74f, 0.28f, 0.24f, 1.f);
    c[ImGuiCol_Separator] = ImVec4(0.26f, 0.26f, 0.30f, 0.75f);
    c[ImGuiCol_ResizeGrip] = ImVec4(0.74f, 0.28f, 0.24f, 0.20f);
    c[ImGuiCol_ResizeGripHovered] = ImVec4(0.74f, 0.28f, 0.24f, 0.55f);
    c[ImGuiCol_ResizeGripActive] = ImVec4(0.94f, 0.72f, 0.30f, 0.86f);
    c[ImGuiCol_Tab] = ImVec4(0.15f, 0.15f, 0.17f, 0.96f);
    c[ImGuiCol_TabHovered] = ImVec4(0.34f, 0.25f, 0.23f, 1.f);
    c[ImGuiCol_TabActive] = ImVec4(0.74f, 0.28f, 0.24f, 1.f);
}

static void initImGuiForWindow() {
    gImguiReady = ImGui::SFML::Init(*gWin);
    if (!gImguiReady) return;

    ImGuiIO& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard;
    io.IniFilename = nullptr;

    io.Fonts->Clear();
    ImFontConfig fontConfig;
    fontConfig.SizePixels = 15.f;
    io.Fonts->AddFontDefault(&fontConfig);
    (void)ImGui::SFML::UpdateFontTexture();
    configureImGuiStyle();
}

static void createWindow(bool fullscreen) {
    if (gImguiReady) {
        ImGui::SFML::Shutdown();
        gImguiReady = false;
    }

    sf::ContextSettings cs;
    cs.antialiasingLevel = 4;
    if (fullscreen) {
        sf::VideoMode dm = sf::VideoMode::getDesktopMode();
        gWin->create(dm, "PFB Studio", sf::Style::Fullscreen, cs);
    } else {
        gWin->create(sf::VideoMode(gWinW, gWinH), "PFB Studio",
                     sf::Style::Resize | sf::Style::Close, cs);
    }
    gWin->setFramerateLimit(60);
    gWin->setKeyRepeatEnabled(true);
    gFullscreen = fullscreen;
    initImGuiForWindow();
}

static void drawCenteredText(const std::string& text, float y, unsigned size,
                             sf::Color color, bool bold = false) {
    (void)bold;
    if (!gImguiReady) return;
    sf::Vector2u ws = gWin->getSize();
    ImFont* font = ImGui::GetFont();
    const ImVec2 textSize = font->CalcTextSizeA(static_cast<float>(size), FLT_MAX, 0.f, text.c_str());
    const ImU32 packed = IM_COL32(color.r, color.g, color.b, color.a);
    ImGui::GetForegroundDrawList()->AddText(font, static_cast<float>(size),
        ImVec2((ws.x - textSize.x) * 0.5f, y - textSize.y * 0.5f), packed, text.c_str());
}

static void renderArtwork() {
    sf::Vector2u ws = gWin->getSize();
    gWin->clear(COL_BG);

    if (hasPreview[activeGen]) {
        const sf::Texture* tex = textureGen(activeGen);
        int nW = nativeW(activeGen);
        int nH = nativeH(activeGen);
        if (tex && nW > 0 && nH > 0) {
            float scale = std::max(ws.x / static_cast<float>(nW), ws.y / static_cast<float>(nH));
            sf::Sprite sp(*tex);
            sp.setScale(scale, scale);
            sp.setPosition((ws.x - nW * scale) * 0.5f, (ws.y - nH * scale) * 0.5f);
            gWin->draw(sp);

            sf::RectangleShape veil(sf::Vector2f(static_cast<float>(ws.x), static_cast<float>(ws.y)));
            veil.setFillColor(sf::Color(0, 0, 0, 52));
            gWin->draw(veil);
        }
    } else {
        sf::RectangleShape bg(sf::Vector2f(static_cast<float>(ws.x), static_cast<float>(ws.y)));
        bg.setFillColor(sf::Color(8, 9, 12));
        gWin->draw(bg);
        drawCenteredText(GEN_LABELS[activeGen], ws.y * 0.48f, 28, sf::Color(218, 220, 228), true);
        drawCenteredText("Generate", ws.y * 0.48f + 34.f, 15, sf::Color(125, 132, 145));
    }

    if (runStates[activeGen] == RunState::Running) {
        const float progress = runProgress(activeGen);
        sf::RectangleShape base(sf::Vector2f(static_cast<float>(ws.x), 3.f));
        base.setPosition(0.f, static_cast<float>(ws.y) - 3.f);
        base.setFillColor(sf::Color(255, 255, 255, 38));
        gWin->draw(base);
        sf::RectangleShape fill(sf::Vector2f(ws.x * progress, 3.f));
        fill.setPosition(0.f, static_cast<float>(ws.y) - 3.f);
        fill.setFillColor(COL_ACCENT);
        gWin->draw(fill);
    }
}

static void drawActionButton(const char* label, bool enabled, float width, const std::function<void()>& fn) {
    if (!enabled) ImGui::BeginDisabled();
    if (ImGui::Button(label, ImVec2(width, 36.f)) && enabled) fn();
    if (!enabled) ImGui::EndDisabled();
}

static void drawPerformancePanel(GenId id) {
    if (!ImGui::CollapsingHeader("Performance")) return;

    const GenPerformance perf = performanceGen(id);
    const bool running = anyRunning();

    if (running) ImGui::BeginDisabled();
    ImGui::Checkbox("Fixed-work benchmark", &params[id].benchmarkMode);
    if (ImGui::IsItemHovered(ImGuiHoveredFlags_AllowWhenDisabled)) {
        ImGui::SetTooltip("Ignores Duration and stops after a fixed amount of generator work.");
    }
    if (ImGui::Button("Run Benchmark", ImVec2(-1.f, 30.f))) {
        params[id].benchmarkMode = true;
        startGen(id, false);
    }
    if (running) ImGui::EndDisabled();

    ImGui::Checkbox("Show live stats", &showLiveStats);

    char targetText[32];
    formatMetric(static_cast<double>(perf.benchmarkTarget), targetText, sizeof(targetText));
    ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f),
        "Benchmark target: %s %s", targetText, perf.unitLabel);
    ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f),
        "Setup is timed separately; pin/replay a seed for comparisons.");

    if (!showLiveStats) return;

    const double renderSeconds = static_cast<double>(elapsedByGen[id]);
    const double setupSeconds = static_cast<double>(setupElapsedByGen[id]);
    const double rate = renderSeconds > 0.0
        ? static_cast<double>(perf.workUnits) / renderSeconds
        : 0.0;

    char workText[32];
    char rateText[32];
    formatMetric(static_cast<double>(perf.workUnits), workText, sizeof(workText));
    formatMetric(rate, rateText, sizeof(rateText));

    ImGui::Spacing();
    ImGui::Text("Work: %s %s", workText, perf.unitLabel);
    ImGui::Text("Setup: %.3f s", setupSeconds);
    ImGui::Text("Render: %.3f s", renderSeconds);
    ImGui::Text("Total: %.3f s", setupSeconds + renderSeconds);
    ImGui::Text("Throughput: %s %s/s", rateText, perf.unitLabel);
}

static void renderInspector() {
    sf::Vector2u ws = gWin->getSize();
    float margin = 14.f;
    float panelW = std::clamp(ws.x * 0.30f, 370.f, 430.f);
    if (ws.x < 980) panelW = std::min(static_cast<float>(ws.x) - margin * 2.f, 390.f);

    ImGui::SetNextWindowPos(ImVec2(ws.x - panelW - margin, margin), ImGuiCond_Always);
    ImGui::SetNextWindowSize(ImVec2(panelW, ws.y - margin * 2.f), ImGuiCond_Always);
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoTitleBar;

    ImGui::Begin("PFB Studio Inspector", nullptr, flags);

    ImGui::TextUnformatted("PFB Studio");
    ImGui::SameLine();
    ImGui::TextColored(stateColor(runStates[activeGen]), "%s", stateLabel(runStates[activeGen]));
    ImGui::SameLine();
    if (ImGui::SmallButton("About")) ImGui::OpenPopup("About PFB Studio");
    ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f), "%s", GEN_LABELS[activeGen]);

    if (ImGui::BeginPopupModal("About PFB Studio", nullptr, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImGui::Text("PFB Studio %s", pfb::kVersion);
        ImGui::Separator();
        ImGui::TextWrapped("Native generative art studio with five renderers.");
        ImGui::Spacing();
        ImGui::TextWrapped("Original generator code Copyright (c) 2020 Dawid Alimowski.");
        ImGui::TextWrapped("Standalone application Copyright (c) 2026 Magnus Petursson.");
        ImGui::TextWrapped("MIT licensed. Third-party notices are included with each distribution.");
        ImGui::Spacing();
        if (ImGui::Button("Close", ImVec2(120.f, 0.f))) ImGui::CloseCurrentPopup();
        ImGui::EndPopup();
    }

    ImGui::Spacing();
    if (anyRunning()) ImGui::BeginDisabled();
    float tabGap = ImGui::GetStyle().ItemSpacing.x;
    float tabW = (ImGui::GetContentRegionAvail().x - tabGap * (GEN_COUNT - 1)) / GEN_COUNT;
    for (int i = 0; i < GEN_COUNT; ++i) {
        ImGui::PushID(i);
        bool selected = activeGen == i;
        if (selected) {
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.74f, 0.28f, 0.24f, 1.f));
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(0.80f, 0.34f, 0.29f, 1.f));
            ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(0.64f, 0.22f, 0.19f, 1.f));
        }
        if (ImGui::Button(GEN_SHORT[i], ImVec2(tabW, 32.f))) {
            activeGen = static_cast<GenId>(i);
            saveStatus.clear();
            saveStatusIsError = false;
        }
        if (selected) ImGui::PopStyleColor(3);
        if (i + 1 < GEN_COUNT) ImGui::SameLine();
        ImGui::PopID();
    }
    if (anyRunning()) ImGui::EndDisabled();

    ImGui::Spacing();
    float actionW = (ImGui::GetContentRegionAvail().x - 8.f) * 0.5f;
    drawActionButton("Generate", !anyRunning(), actionW, [] { startGen(activeGen, false); });
    ImGui::SameLine();
    bool canReplay = !anyRunning() && lastSeeds[activeGen] != 0;
    drawActionButton("Replay Seed", canReplay, actionW, [] { startGen(activeGen, true); });
    if (anyRunning()) {
        if (ImGui::Button("Stop", ImVec2(-1.f, 34.f))) stopGen();
    }
    ImGui::Spacing();
    drawActionButton("Save Image", canSaveActiveImage(), -1.f, [] { saveActiveImage(); });
    if (!saveStatus.empty()) {
        ImVec4 statusColor = saveStatusIsError
            ? ImVec4(0.88f, 0.39f, 0.39f, 1.f)
            : ImVec4(0.58f, 0.62f, 0.70f, 1.f);
        ImGui::PushStyleColor(ImGuiCol_Text, statusColor);
        ImGui::TextWrapped("%s", saveStatus.c_str());
        ImGui::PopStyleColor();
    }

    const float progress = runStates[activeGen] == RunState::Complete
        ? 1.f
        : runProgress(activeGen);
    char progressText[128];
    if (params[activeGen].benchmarkMode) {
        const GenPerformance perf = performanceGen(activeGen);
        char workText[32];
        char targetText[32];
        formatMetric(static_cast<double>(perf.workUnits), workText, sizeof(workText));
        formatMetric(static_cast<double>(perf.benchmarkTarget), targetText, sizeof(targetText));
        std::snprintf(progressText, sizeof(progressText), "%s / %s %s",
                      workText, targetText, perf.unitLabel);
    } else {
        const float target = params[activeGen].duration > 0
            ? static_cast<float>(params[activeGen].duration)
            : DEFAULTS[activeGen].duration;
        std::snprintf(progressText, sizeof(progressText), "%.0fs / %.0fs", elapsedByGen[activeGen], target);
    }
    ImGui::ProgressBar(progress, ImVec2(-1.f, 8.f), "");
    ImGui::TextColored(ImVec4(0.58f, 0.62f, 0.70f, 1.f), "%s", progressText);

    if (runStates[activeGen] == RunState::Error && !errors[activeGen].empty()) {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.88f, 0.39f, 0.39f, 1.f));
        ImGui::TextWrapped("%s", errors[activeGen].c_str());
        ImGui::PopStyleColor();
    }

    ImGui::Spacing();
    drawPerformancePanel(activeGen);

    ImGui::Spacing();
    ImGui::Separator();
    ImGui::Spacing();

    if (anyRunning()) ImGui::BeginDisabled();
    drawSeedWidget(activeGen);

    ImGui::Spacing();
    if (ImGui::Button("Reset Parameters", ImVec2(-1.f, 32.f))) resetParams(activeGen);
    if (anyRunning()) ImGui::EndDisabled();

    ImGui::Spacing();
    ImGui::Separator();

    if (anyRunning()) ImGui::BeginDisabled();
    ImGui::BeginChild("params", ImVec2(0.f, 0.f), false, ImGuiWindowFlags_AlwaysUseWindowPadding);
    drawParams(activeGen);
    ImGui::EndChild();
    if (anyRunning()) ImGui::EndDisabled();

    ImGui::End();
}

static void renderFrame() {
    renderArtwork();
    if (gImguiReady) {
        renderInspector();
        ImGui::SFML::Render(*gWin);
    }
    gWin->display();
}

static int runSmokeTest(const std::filesystem::path& outputDirectory) {
    std::error_code ec;
    std::filesystem::create_directories(outputDirectory, ec);
    if (ec) {
        std::cerr << "Could not create smoke-test directory: " << outputDirectory << '\n';
        return 2;
    }

    std::ofstream report(outputDirectory / "report.json", std::ios::trunc);
    if (!report) return 2;
    report << "{\n  \"version\": \"" << pfb::kVersion << "\",\n  \"generators\": [\n";

    bool allPassed = true;
    for (int index = 0; index < GEN_COUNT; ++index) {
        const GenId id = static_cast<GenId>(index);
        params[id] = GenParams{};
        params[id].seed = 424242u + static_cast<std::uint64_t>(index);
        params[id].duration = 0.5;
        params[id].outputW = 512;
        params[id].outputH = 512;
        if (id == GEN_PERLIN) {
            params[id].aspect = 3;
            params[id].customAspectW = 256;
            params[id].customAspectH = 256;
        }
        if (id == GEN_FRACTAL) params[id].preprocessTime = 0.1;

        const bool started = startGen(id, false);
        while (anyRunning()) stepRunningGen();

        bool passed = started && runStates[id] == RunState::Complete;
        std::string error = errors[id];
        std::filesystem::path imagePath = outputDirectory / (std::string(GEN_SLUGS[id]) + ".png");
        if (passed) {
            const sf::Texture* texture = textureGen(id);
            sf::Image image = texture ? texture->copyToImage() : sf::Image{};
            passed = texture && image.getSize().x > 0 && image.getSize().y > 0 && pfb::imageHasVariation(image);
            if (passed && !pfb::writeImage(image, imagePath, error)) passed = false;
            if (!passed && error.empty()) error = "Generated image was empty or uniform.";
        }
        allPassed = allPassed && passed;
        report << "    {\"name\": \"" << GEN_SLUGS[id] << "\", \"passed\": "
               << (passed ? "true" : "false") << ", \"error\": \"" << error << "\"}"
               << (index + 1 < GEN_COUNT ? "," : "") << "\n";
    }
    report << "  ],\n  \"passed\": " << (allPassed ? "true" : "false") << "\n}\n";
    return allPassed ? 0 : 1;
}

int main(int argc, char* argv[]) {
    if (argc >= 2 && std::string(argv[1]) == "--version") {
        std::cout << pfb::kAppName << ' ' << pfb::kVersion << '\n';
        return 0;
    }
    if (argc >= 2 && std::string(argv[1]) == "--smoke-test") {
        if (argc < 3) {
            std::cerr << "--smoke-test requires an output directory.\n";
            return 2;
        }
        return runSmokeTest(argv[2]);
    }

    sf::RenderWindow win;
    gWin = &win;
    createWindow(false);

    sf::Clock deltaClock;
    while (win.isOpen()) {
        sf::Event ev;
        while (win.pollEvent(ev)) {
            if (gImguiReady) ImGui::SFML::ProcessEvent(win, ev);

            switch (ev.type) {
                case sf::Event::Closed:
                    win.close();
                    break;
                case sf::Event::Resized:
                    if (!gFullscreen) {
                        gWinW = static_cast<int>(ev.size.width);
                        gWinH = static_cast<int>(ev.size.height);
                    }
                    win.setView(sf::View(sf::FloatRect(0, 0,
                        static_cast<float>(ev.size.width),
                        static_cast<float>(ev.size.height))));
                    break;
                case sf::Event::KeyPressed:
                    if (ev.key.code == sf::Keyboard::F11) {
                        createWindow(!gFullscreen);
                        deltaClock.restart();
                    } else if (ev.key.code == sf::Keyboard::Escape) {
                        if (anyRunning()) stopGen();
                        else if (gFullscreen) createWindow(false);
                    }
                    break;
                default:
                    break;
            }
        }

        stepRunningGen();

        if (gImguiReady) ImGui::SFML::Update(win, deltaClock.restart());
        else deltaClock.restart();

        if (!anyRunning()) sf::sleep(sf::milliseconds(2));
        renderFrame();
    }

    if (gImguiReady) ImGui::SFML::Shutdown();
    return 0;
}
