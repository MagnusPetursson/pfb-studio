#pragma once

#include <filesystem>
#include <string>

namespace pfb {

enum class DialogStatus { Accepted, Canceled, Error };

struct SaveDialogResult {
    DialogStatus status = DialogStatus::Error;
    std::filesystem::path path;
    std::string error;
};

std::filesystem::path picturesDirectory();
SaveDialogResult chooseImageSavePath(const std::filesystem::path& suggestedPath);

}
