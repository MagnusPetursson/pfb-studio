#pragma once

#include <SFML/Graphics/Image.hpp>

#include <filesystem>
#include <string>

namespace pfb {

std::filesystem::path normalizeImagePath(std::filesystem::path path);
std::filesystem::path defaultImagePath(const std::string& generator, std::uint64_t seed);
bool writeImage(const sf::Image& image, const std::filesystem::path& path, std::string& error);
bool imageHasVariation(const sf::Image& image);

}
