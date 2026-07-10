#include "app_support.hpp"
#include "platform.hpp"

#include <SFML/Graphics/Image.hpp>

#include <cassert>
#include <filesystem>
#include <string>

int main() {
    using namespace pfb;
    assert(normalizeImagePath("art").extension() == ".png");
    assert(normalizeImagePath("art.PNG").extension() == ".PNG");
    assert(normalizeImagePath("art.jpeg").extension() == ".jpeg");
    assert(normalizeImagePath("art.bmp").extension() == ".png");

    sf::Image image;
    image.create(2, 2, sf::Color::Black);
    image.setPixel(1, 1, sf::Color::White);
    assert(imageHasVariation(image));

    const std::filesystem::path root = std::filesystem::temp_directory_path() / "pfb support test";
    const std::filesystem::path output = root / "unicode-islenska-aeoiu.png";
    std::string error;
    assert(writeImage(image, output, error));
    assert(std::filesystem::file_size(output) > 0);
    std::filesystem::remove_all(root);
    return 0;
}
