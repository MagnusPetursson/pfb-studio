cmake_minimum_required(VERSION 3.22)

project(PFBStudio VERSION 0.1.0 LANGUAGES CXX)

include(FetchContent)
include(GNUInstallDirs)
include(CTest)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(MSVC)
    set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>" CACHE STRING "" FORCE)
endif()
set(BUILD_SHARED_LIBS OFF CACHE BOOL "Build static dependencies" FORCE)
set(SFML_BUILD_AUDIO OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_NETWORK OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SFML_BUILD_DOC OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
    sfml
    GIT_REPOSITORY https://github.com/SFML/SFML.git
    GIT_TAG 5383d2b3948f805af55c9f8a4587ac72ec5981d1 # SFML 2.6.2
    GIT_SHALLOW TRUE
    SOURCE_SUBDIR cmake/unused
)
FetchContent_MakeAvailable(sfml)
if(MINGW)
    set(FREETYPE_INCLUDE_DIR_ft2build "${sfml_SOURCE_DIR}/extlibs/headers/freetype2" CACHE PATH "" FORCE)
    set(FREETYPE_INCLUDE_DIR_freetype2 "${sfml_SOURCE_DIR}/extlibs/headers/freetype2" CACHE PATH "" FORCE)
    set(FREETYPE_LIBRARY "${sfml_SOURCE_DIR}/extlibs/libs-mingw/x64/libfreetype.a" CACHE FILEPATH "" FORCE)
endif()
add_subdirectory(${sfml_SOURCE_DIR} ${sfml_BINARY_DIR} EXCLUDE_FROM_ALL)

FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui.git
    GIT_TAG c6e0284ac58b3f205c95365478888f7b53b077e2 # Dear ImGui 1.89.9
    GIT_SHALLOW TRUE
    SOURCE_SUBDIR cmake/unused
)
FetchContent_MakeAvailable(imgui)

FetchContent_Declare(
    imgui_sfml
    GIT_REPOSITORY https://github.com/SFML/imgui-sfml.git
    GIT_TAG 64e09feda29266572799e5ded66eac5cb0a749aa # ImGui-SFML 2.6.1
    GIT_SHALLOW TRUE
    SOURCE_SUBDIR cmake/unused
)
FetchContent_MakeAvailable(imgui_sfml)

find_package(OpenGL REQUIRED)

add_library(pfb-imgui STATIC
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
)
target_include_directories(pfb-imgui PUBLIC
    ${imgui_SOURCE_DIR}
    ${imgui_sfml_SOURCE_DIR}
    ${sfml_SOURCE_DIR}/include
)
target_compile_definitions(pfb-imgui PUBLIC IMGUI_USER_CONFIG="imconfig-SFML.h")

add_library(pfb-imgui-sfml STATIC ${imgui_sfml_SOURCE_DIR}/imgui-SFML.cpp)
target_include_directories(pfb-imgui-sfml PUBLIC
    ${imgui_SOURCE_DIR}
    ${imgui_sfml_SOURCE_DIR}
)
target_compile_definitions(pfb-imgui-sfml PUBLIC IMGUI_USER_CONFIG="imconfig-SFML.h")
target_link_libraries(pfb-imgui-sfml PUBLIC pfb-imgui sfml-graphics sfml-window sfml-system OpenGL::GL)

set(PFB_SOURCES
    src/app/main.cpp
    src/app/app_support.cpp
    src/app/platform.cpp
    src/generators/gen_perlin.cpp
    src/generators/gen_fractal.cpp
    src/generators/gen_circle.cpp
    src/generators/gen_fujii.cpp
    src/generators/gen_galaxies.cpp
    src/legacy/FastNoise.cpp
)

if(WIN32)
    configure_file(packaging/windows/pfb-studio.rc.in ${CMAKE_CURRENT_BINARY_DIR}/pfb-studio.rc @ONLY)
    add_executable(pfb-studio WIN32 ${PFB_SOURCES} ${CMAKE_CURRENT_BINARY_DIR}/pfb-studio.rc)
else()
    add_executable(pfb-studio ${PFB_SOURCES})
endif()

target_include_directories(pfb-studio PRIVATE src/app src/generators src/legacy)
target_compile_definitions(pfb-studio PRIVATE PFB_VERSION="${PROJECT_VERSION}")
target_link_libraries(pfb-studio PRIVATE pfb-imgui-sfml sfml-graphics sfml-window sfml-system)

if(MSVC)
    target_compile_options(pfb-studio PRIVATE /W3 /permissive-)
    # The Windows resource script already embeds packaging/windows/pfb-studio.manifest
    # as RT_MANIFEST resource 1. Suppress the linker's default manifest to avoid a
    # duplicate resource on current MSVC toolchains.
    target_link_options(pfb-studio PRIVATE /MANIFEST:NO)
elseif(MINGW)
    target_compile_options(pfb-studio PRIVATE -Wall -Wextra)
    target_link_options(pfb-studio PRIVATE -static -static-libgcc -static-libstdc++)
else()
    target_compile_options(pfb-studio PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(NOT MSVC)
    set_source_files_properties(
        src/generators/gen_perlin.cpp
        src/generators/gen_fractal.cpp
        src/generators/gen_circle.cpp
        src/generators/gen_fujii.cpp
        src/generators/gen_galaxies.cpp
        src/legacy/FastNoise.cpp
        PROPERTIES COMPILE_OPTIONS "-w"
    )
endif()

if(WIN32)
    target_link_libraries(pfb-studio PRIVATE sfml-main ole32 shell32 uuid)
    set_target_properties(pfb-studio PROPERTIES OUTPUT_NAME PFBStudio)
else()
    set_target_properties(pfb-studio PROPERTIES OUTPUT_NAME pfb-studio)
endif()

install(TARGETS pfb-studio RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
if(UNIX AND NOT APPLE)
    install(FILES packaging/linux/is.magnusp.pfbstudio.desktop
        DESTINATION ${CMAKE_INSTALL_DATADIR}/applications)
    install(FILES assets/pfb-studio.svg
        DESTINATION ${CMAKE_INSTALL_DATADIR}/icons/hicolor/scalable/apps
        RENAME is.magnusp.pfbstudio.svg)
    install(FILES packaging/linux/is.magnusp.pfbstudio.appdata.xml
        DESTINATION ${CMAKE_INSTALL_DATADIR}/metainfo)
endif()
install(FILES LICENSE THIRD_PARTY_NOTICES.md
    DESTINATION ${CMAKE_INSTALL_DATADIR}/doc/pfb-studio)

if(BUILD_TESTING)
    add_executable(pfb-support-tests tests/support_tests.cpp src/app/app_support.cpp src/app/platform.cpp)
    target_include_directories(pfb-support-tests PRIVATE src/app)
    target_link_libraries(pfb-support-tests PRIVATE sfml-graphics sfml-system)
    if(WIN32)
        target_link_libraries(pfb-support-tests PRIVATE ole32 shell32 uuid)
    endif()
    target_compile_definitions(pfb-support-tests PRIVATE PFB_TESTING=1)
    add_test(NAME pfb-support-tests COMMAND pfb-support-tests)
endif()

set(CPACK_PACKAGE_NAME "pfb-studio")
set(CPACK_PACKAGE_VENDOR "Magnus Petursson")
set(CPACK_PACKAGE_CONTACT "magnus@magnusp.is")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Native generative art studio")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_CURRENT_SOURCE_DIR}/LICENSE")
set(CPACK_DEBIAN_PACKAGE_SECTION "graphics")
set(CPACK_DEBIAN_PACKAGE_PRIORITY "optional")
set(CPACK_DEBIAN_PACKAGE_SHLIBDEPS ON)
set(CPACK_DEBIAN_PACKAGE_RECOMMENDS "zenity")
set(CPACK_DEBIAN_FILE_NAME DEB-DEFAULT)
include(CPack)
