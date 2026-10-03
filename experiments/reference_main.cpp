#include "generator.hpp"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
struct Generator {
    const char* name;
    bool (*start)(const GenParams&, std::string&);
    bool (*step)();
    const sf::Texture& (*texture)();
    GenPerformance (*performance)();
};
const Generator generators[] = {
    {"perlin", perlin_start, perlin_step, perlin_texture, perlin_performance},
    {"fractal", fractal_start, fractal_step, fractal_texture, fractal_performance},
    {"circle", circle_start, circle_step, circle_texture, circle_performance},
    {"fujii", fujii_start, fujii_step, fujii_texture, fujii_performance},
    {"galaxies", galaxies_start, galaxies_step, galaxies_texture, galaxies_performance}
};
}

int main(int argc, char** argv) {
    try {
        if (argc != 4) throw std::runtime_error("Usage: pfb-reference-render GENERATOR SEED OUTPUT.png");
        const Generator* generator = nullptr;
        for (const auto& g : generators) if (g.name == std::string(argv[1])) generator = &g;
        if (!generator) throw std::runtime_error("Unknown generator");
        const std::string seedText(argv[2]);
        if (seedText.empty() || seedText.find_first_not_of("0123456789") != std::string::npos)
            throw std::runtime_error("Seed must be an unsigned integer");
        GenParams parameters;
        parameters.seed = std::stoull(seedText);
        if (!parameters.seed) throw std::runtime_error("Seed zero is automatic; use a fixed nonzero seed");
        // Keep the original aspect, native dimensions, duration, preprocessing,
        // palette, and final effects. In particular, never enable benchmark mode.
        const auto output = std::filesystem::path(argv[3]);
        if (output.has_parent_path()) std::filesystem::create_directories(output.parent_path());
        using Clock = std::chrono::steady_clock;
        const auto begin = Clock::now();
        std::string error;
        if (!generator->start(parameters, error)) throw std::runtime_error(error);
        const auto started = Clock::now();
        std::uint64_t ticks = 0;
        for (;;) {
            const bool more = generator->step();
            ++ticks;
            if (!more) break;
            if (std::chrono::duration<double>(Clock::now() - started).count() > 150)
                throw std::runtime_error("Reference render exceeded 150 seconds");
        }
        const auto ended = Clock::now();
        const auto image = generator->texture().copyToImage();
        if (!image.saveToFile(output.string())) throw std::runtime_error("Could not save image");
        const auto size = image.getSize();
        const auto performance = generator->performance();
        auto metadata = output;
        metadata.replace_extension(".json");
        std::ofstream json(metadata);
        if (!json) throw std::runtime_error("Could not save metadata");
        json << "{\"kind\":\"original\",\"generator\":\"" << generator->name
             << "\",\"seed\":" << parameters.seed << ",\"mode\":\"normal-native-defaults\""
             << ",\"width\":" << size.x << ",\"height\":" << size.y
             << ",\"ticks\":" << ticks << ",\"work\":" << performance.workUnits
             << ",\"setup_seconds\":" << std::chrono::duration<double>(started-begin).count()
             << ",\"render_seconds\":" << std::chrono::duration<double>(ended-started).count()
             << "}\n";
        std::cout << generator->name << " seed=" << parameters.seed << " " << size.x << "x" << size.y
                  << " work=" << performance.workUnits << " saved=" << output.string() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
