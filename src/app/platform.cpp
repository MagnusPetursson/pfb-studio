#include "platform.hpp"

#include <array>
#include <cstdlib>
#include <fstream>
#include <sstream>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <knownfolders.h>
#include <shlobj.h>
#include <shobjidl.h>
#else
#include <cstdio>
#endif

namespace pfb {
namespace {

#ifndef _WIN32
std::string shellQuote(const std::string& value) {
    std::string quoted = "'";
    for (char ch : value) quoted += ch == '\'' ? "'\\''" : std::string(1, ch);
    return quoted + "'";
}

bool commandAvailable(const char* command) {
    return std::system((std::string("command -v ") + command + " >/dev/null 2>&1").c_str()) == 0;
}
#endif

}

std::filesystem::path picturesDirectory() {
#ifdef _WIN32
    PWSTR path = nullptr;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Pictures, KF_FLAG_DEFAULT, nullptr, &path))) {
        std::filesystem::path result(path);
        CoTaskMemFree(path);
        return result;
    }
    if (const char* profile = std::getenv("USERPROFILE")) return std::filesystem::path(profile) / "Pictures";
    return std::filesystem::current_path();
#else
    const char* homeValue = std::getenv("HOME");
    const std::filesystem::path home = homeValue ? homeValue : std::filesystem::current_path();
    const char* configValue = std::getenv("XDG_CONFIG_HOME");
    const std::filesystem::path config = configValue ? configValue : home / ".config";
    std::ifstream input(config / "user-dirs.dirs");
    std::string line;
    while (std::getline(input, line)) {
        constexpr const char* prefix = "XDG_PICTURES_DIR=\"";
        if (line.rfind(prefix, 0) != 0 || line.size() <= std::char_traits<char>::length(prefix)) continue;
        std::string value = line.substr(std::char_traits<char>::length(prefix));
        if (!value.empty() && value.back() == '"') value.pop_back();
        const std::string marker = "$HOME";
        if (value.rfind(marker, 0) == 0) value.replace(0, marker.size(), home.string());
        if (!value.empty()) return value;
    }
    return home / "Pictures";
#endif
}

SaveDialogResult chooseImageSavePath(const std::filesystem::path& suggestedPath) {
#ifdef _WIN32
    const HRESULT initResult = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    const bool shouldUninitialize = SUCCEEDED(initResult);
    IFileSaveDialog* dialog = nullptr;
    HRESULT result = CoCreateInstance(CLSID_FileSaveDialog, nullptr, CLSCTX_INPROC_SERVER,
        IID_PPV_ARGS(&dialog));
    if (FAILED(result)) {
        if (shouldUninitialize) CoUninitialize();
        return {DialogStatus::Error, {}, "Could not create the Windows save dialog."};
    }

    const COMDLG_FILTERSPEC filters[] = {
        {L"PNG image", L"*.png"},
        {L"JPEG image", L"*.jpg;*.jpeg"}
    };
    dialog->SetFileTypes(2, filters);
    dialog->SetFileTypeIndex(1);
    dialog->SetDefaultExtension(L"png");
    dialog->SetFileName(suggestedPath.filename().c_str());

    IShellItem* folder = nullptr;
    if (SUCCEEDED(SHCreateItemFromParsingName(suggestedPath.parent_path().c_str(), nullptr,
            IID_PPV_ARGS(&folder)))) {
        dialog->SetFolder(folder);
        folder->Release();
    }

    result = dialog->Show(nullptr);
    if (result == HRESULT_FROM_WIN32(ERROR_CANCELLED)) {
        dialog->Release();
        if (shouldUninitialize) CoUninitialize();
        return {DialogStatus::Canceled, {}, {}};
    }
    if (FAILED(result)) {
        dialog->Release();
        if (shouldUninitialize) CoUninitialize();
        return {DialogStatus::Error, {}, "The Windows save dialog failed."};
    }

    IShellItem* item = nullptr;
    PWSTR selected = nullptr;
    result = dialog->GetResult(&item);
    if (SUCCEEDED(result)) result = item->GetDisplayName(SIGDN_FILESYSPATH, &selected);
    std::filesystem::path path;
    if (SUCCEEDED(result) && selected) path = selected;
    if (selected) CoTaskMemFree(selected);
    if (item) item->Release();
    dialog->Release();
    if (shouldUninitialize) CoUninitialize();
    if (path.empty()) return {DialogStatus::Error, {}, "Could not read the selected path."};
    return {DialogStatus::Accepted, path, {}};
#else
#ifdef PFB_TESTING
    return {DialogStatus::Accepted, suggestedPath, {}};
#else
    if (!commandAvailable("zenity")) return {DialogStatus::Accepted, suggestedPath, {}};
    std::string command = "zenity --file-selection --save --confirm-overwrite";
    command += " --title=" + shellQuote("Save PFB image");
    command += " --filename=" + shellQuote(suggestedPath.string());
    command += " --file-filter=" + shellQuote("Images | *.png *.jpg *.jpeg");
    command += " 2>/dev/null";
    FILE* pipe = popen(command.c_str(), "r");
    if (!pipe) return {DialogStatus::Error, {}, "Could not open the save dialog."};
    std::array<char, 512> buffer{};
    std::string output;
    while (fgets(buffer.data(), static_cast<int>(buffer.size()), pipe)) output += buffer.data();
    const int status = pclose(pipe);
    while (!output.empty() && (output.back() == '\n' || output.back() == '\r')) output.pop_back();
    if (output.empty()) return {DialogStatus::Canceled, {}, {}};
    if (status != 0) return {DialogStatus::Error, {}, "The save dialog failed."};
    return {DialogStatus::Accepted, output, {}};
#endif
#endif
}

}
