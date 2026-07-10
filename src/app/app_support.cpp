#include "app_support.hpp"

#include "platform.hpp"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <vector>

namespace pfb {
namespace {

std::string lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return value;
}

}

std::filesystem::path normalizeImagePath(std::filesystem::path path) {
    const std::string extension = lower(path.extension().string());
    if (extension.empty()) return path.replace_extension(".png");
    if (extension == ".png" || extension == ".jpg" || extension == ".jpeg") return path;
    return path.replace_extension(".png");
}

std::filesystem::path defaultImagePath(const std::string& generator, std::uint64_t seed) {
    const std::string seedPart = seed == 0 ? "preview" : std::to_string(seed);
    return picturesDirectory() / "PFB Studio" / ("pfb-" + generator + "-" + seedPart + ".png");
}

bool writeImage(const sf::Image& image, const std::filesystem::path& rawPath, std::string& error) {
    const std::filesystem::path path = normalizeImagePath(rawPath);
    std::error_code ec;
    if (path.has_parent_path()) std::filesystem::create_directories(path.parent_path(), ec);
    if (ec) {
        error = "Could not create folder: " + path.parent_path().string();
        return false;
    }

    const std::string extension = lower(path.extension().string());
    const std::string format = extension == ".png" ? "png" : "jpg";
    std::vector<sf::Uint8> encoded;
    if (!image.saveToMemory(encoded, format)) {
        error = "Could not encode image as " + format + ".";
        return false;
    }

    std::ofstream output(path, std::ios::binary | std::ios::trunc);
    if (!output) {
        error = "Could not open output file: " + path.string();
        return false;
    }
    output.write(reinterpret_cast<const char*>(encoded.data()), static_cast<std::streamsize>(encoded.size()));
    if (!output) {
        error = "Could not write output file: " + path.string();
        return false;
    }
    return true;
}

bool imageHasVariation(const sf::Image& image) {
    const sf::Vector2u size = image.getSize();
    if (size.x == 0 || size.y == 0) return false;
    const sf::Color first = image.getPixel(0, 0);
    const unsigned stepX = std::max(1u, size.x / 32u);
    const unsigned stepY = std::max(1u, size.y / 32u);
    for (unsigned y = 0; y < size.y; y += stepY) {
        for (unsigned x = 0; x < size.x; x += stepX) {
            if (image.getPixel(x, y) != first) return true;
        }
    }
    return false;
}

}
