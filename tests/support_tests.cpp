#include "app_support.hpp"

#include <SFML/Graphics/Image.hpp>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>
#include <vector>

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) throw std::runtime_error(message);
}

class TemporaryDirectory {
public:
    TemporaryDirectory() {
        const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
        for (unsigned attempt = 0; attempt < 100; ++attempt) {
            const auto candidate = std::filesystem::temp_directory_path() /
                ("pfb-support-tests-" + std::to_string(stamp) + "-" + std::to_string(attempt));
            if (std::filesystem::create_directory(candidate)) {
                path = candidate;
                return;
            }
        }
        throw std::runtime_error("Could not create a unique test directory.");
    }

    ~TemporaryDirectory() {
        std::error_code ignored;
        std::filesystem::remove_all(path, ignored);
    }

    std::filesystem::path path;
};

sf::Image readImage(const std::filesystem::path& path) {
    // Read through filesystem::path so Unicode filenames work on Windows too.
    std::ifstream input(path, std::ios::binary);
    require(input.is_open(), "Saved image could not be opened.");
    const std::vector<char> bytes{std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
    require(!bytes.empty(), "Saved image was empty.");
    sf::Image result;
    require(result.loadFromMemory(bytes.data(), bytes.size()), "Saved image could not be decoded.");
    return result;
}

void runTests() {
    using namespace pfb;
    require(normalizeImagePath("art").extension() == ".png", "Missing extensions should become PNG.");
    require(normalizeImagePath("art.PNG").extension() == ".PNG", "PNG extensions should preserve case.");
    require(normalizeImagePath("art.jpg").extension() == ".jpg", "JPG should be supported.");
    require(normalizeImagePath("art.jpeg").extension() == ".jpeg", "JPEG should be supported.");
    require(normalizeImagePath("art.JPEG").extension() == ".JPEG", "JPEG extensions should preserve case.");
    require(normalizeImagePath("art.bmp").extension() == ".png", "Unsupported extensions should become PNG.");
    require(defaultImagePath("perlin", 42).filename() == "pfb-perlin-42.png", "Default filenames should include the seed.");
    require(defaultImagePath("perlin", 0).filename() == "pfb-perlin-preview.png", "Unset seeds should use a preview filename.");

    sf::Image image;
    require(!imageHasVariation(image), "An empty image should not have variation.");
    image.create(2, 2, sf::Color::Black);
    require(!imageHasVariation(image), "A uniform image should not have variation.");
    image.setPixel(1, 1, sf::Color::White);
    require(imageHasVariation(image), "A nonuniform image should have variation.");
    image.setPixel(1, 0, sf::Color(23, 101, 207, 63));

    TemporaryDirectory directory;
    const auto output = directory.path / "nested folder" /
        std::filesystem::u8path(u8"\u00edslenska-\u00e6\u00f6.png");
    std::string error;
    const bool pngWritten = writeImage(image, output, error);
    require(pngWritten, "PNG export failed: " + error);
    const sf::Image png = readImage(output);
    require(png.getSize() == image.getSize(), "PNG export changed the dimensions.");
    for (unsigned y = 0; y < image.getSize().y; ++y)
        for (unsigned x = 0; x < image.getSize().x; ++x)
            require(png.getPixel(x, y) == image.getPixel(x, y), "PNG export changed a pixel or its alpha.");

    const auto jpegPath = directory.path / "image.JPEG";
    const bool jpegWritten = writeImage(image, jpegPath, error);
    require(jpegWritten, "JPEG export failed: " + error);
    require(readImage(jpegPath).getSize() == image.getSize(), "JPEG export changed the dimensions.");

    const auto unsupportedPath = directory.path / "image.bmp";
    const bool normalizedWritten = writeImage(image, unsupportedPath, error);
    require(normalizedWritten, "Normalized PNG export failed: " + error);
    require(!std::filesystem::exists(unsupportedPath), "An unsupported extension should not be written.");
    require(readImage(directory.path / "image.png").getPixel(1, 0) == image.getPixel(1, 0),
            "Normalized PNG export did not preserve pixels.");

    const auto blockerPath = directory.path / "file-instead-of-directory";
    std::ofstream blocker(blockerPath);
    require(blocker.is_open(), "Could not create the export failure fixture.");
    blocker.close();
    error.clear();
    require(!writeImage(image, blockerPath / "image.png", error), "Export under a regular file should fail.");
    require(!error.empty(), "Failed exports should explain the failure.");
}

} // namespace

int main() {
    try {
        runTests();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Support test failed: " << error.what() << '\n';
        return 1;
    }
}
