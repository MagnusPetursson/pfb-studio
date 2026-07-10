// preinclude.hpp — Pre-include every system/library header that the generator
// source trees need, at file scope.  This fires all include guards *before*
// any anonymous namespace, preventing types from landing in
// {anonymous}::sf:: or {anonymous}::std:: instead of global sf:: / std::.
//
// Rules:
//  • Only system, SFML, and external library headers go here.
//  • Local project headers (aural.hpp, math.hpp, …) must stay INSIDE the
//    anonymous namespace so they get internal linkage.
#pragma once

// ── Standard library ────────────────────────────────────────────────────────
// The legacy generators are included inside anonymous namespaces. Pre-include
// their standard-library surface globally so the wrapper also works on MSVC.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <queue>
#include <random>
#include <set>
#include <sstream>
#include <string>
#include <type_traits>
#include <unordered_map>
#include <utility>
#include <vector>

// ── SFML ────────────────────────────────────────────────────────────────────
#include <SFML/Graphics.hpp>
#include <SFML/System.hpp>

// ── FastNoise ────────────────────────────────────────────────────────────────
// FastNoise.h declares class FastNoise whose methods are implemented in
// FastNoise.cpp (compiled as a global TU).  If FastNoise.h were processed
// inside an anonymous namespace the mangled names for its methods would differ
// and the linker would emit "undefined reference" errors.
#include "../legacy/FastNoise.h"

// ── PerlinNoise (siv::) ──────────────────────────────────────────────────────
// Used only by perlin.cpp, but safe to include everywhere.
#include "../legacy/PerlinNoise.h"
