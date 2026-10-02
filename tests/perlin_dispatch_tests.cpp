// Exercise the production tree builder and resolver.
#include "../src/generators/gen_perlin.cpp"

#include <stdexcept>

namespace {

// The pre-cache resolver is the compatibility oracle. Keep its nested call
// expressions intact: Julia variations consume RNG and child order matters.
sf::Vector2f resolveReference(int u, sf::Vector2f v, double amount,
                             std::vector<std::vector<int>>& tree, std::vector<node>& nodes) {
    node U = nodes[u];
    if (!tree[u].size()) {
        if (U.type == 0) return sf::Vector2f(truncations[U.var](v), 0);
        else return variations[U.var](v, amount);
    } else if (U.type < 4) {
        switch (U.type) {
            case 0: return sf::Vector2f(truncations[U.var](resolveReference(tree[u][0], v, amount, tree, nodes)), 0);
            case 1: return variations[U.var](resolveReference(tree[u][0], v, amount, tree, nodes), amount);
            case 2: return extrapolations[U.var](resolveReference(tree[u][0], v, amount, tree, nodes).x, amount);
            case 3: return sf::Vector2f(transformations[U.var](resolveReference(tree[u][0], v, amount, tree, nodes).x), 0);
        }
    } else {
        switch (U.operation) {
            case '+': return addF(resolveReference(tree[u][0], v, amount, tree, nodes), resolveReference(tree[u][1], v, amount, tree, nodes));
            case '-': return subF(resolveReference(tree[u][0], v, amount, tree, nodes), resolveReference(tree[u][1], v, amount, tree, nodes));
            case '*': return mulF(resolveReference(tree[u][0], v, amount, tree, nodes), resolveReference(tree[u][1], v, amount, tree, nodes));
            case '/': return divF(resolveReference(tree[u][0], v, amount, tree, nodes), resolveReference(tree[u][1], v, amount, tree, nodes));
        }
    }
    return v;
}

void compareResolution(std::vector<std::vector<int>>& tree, std::vector<node>& nodes,
                       sf::Vector2f input, double amount) {
    const auto before = gen;
    const auto expected = resolveReference(1, input, amount, tree, nodes);
    const auto expectedRandomState = gen;
    gen = before;
    const auto actual = resolveFieldTree2(1, input, amount, tree, nodes);
    if (std::memcmp(&expected.x, &actual.x, sizeof(float)) != 0 ||
        std::memcmp(&expected.y, &actual.y, sizeof(float)) != 0 || gen != expectedRandomState)
        throw std::runtime_error("Cached Perlin dispatch changed result bits or random state");
}

void checkTypes(int u, const std::vector<std::vector<int>>& tree,
                const std::vector<node>& nodes, std::array<bool, 5>& covered) {
    covered[nodes[u].type] = true;
    for (int child : tree[u]) checkTypes(child, tree, nodes, covered);
}

void runTests() {
    std::array<bool, 5> covered{};
    for (int preset = 0; preset < FLOW_PRESET_COUNT; ++preset) {
        for (const auto seed : {1ull, 42ull, 314159ull, 271828ull, 424242ull, 987654ull}) {
            GenParams params;
            params.flowPreset = preset;
            seedgen(seed);
            setup();
            applyPerlinParams(params);
            pn.SetNoiseType(FastNoise::PerlinFractal);
            pn.SetFractalOctaves(octaves);
            pn.SetSeed(static_cast<int>(seed));
            checkTypes(1, tree1, nodes1, covered);
            for (int sample = 0; sample < 64; ++sample) {
                const sf::Vector2f input((sample - 29) * 0.073f, (sample % 11 - 5) * 0.137f);
                compareResolution(tree1, nodes1, input, sample % 2 ? 0.4 : 1.0);
            }
        }
    }
    if (!std::all_of(covered.begin(), covered.end(), [](bool value) { return value; }))
        throw std::runtime_error("Preset coverage omitted a field-tree node type");

    // Both operation branches consume random samples; reversing child
    // evaluation order changes their results even when the final RNG matches.
    for (const char operation : {'+', '-', '*', '/'}) {
        std::vector<std::vector<int>> tree(5);
        std::vector<node> nodes(5);
        nodes[1] = node(4, operation, "unused");
        nodes[2] = node(1, '0', "julia");
        nodes[3] = node(1, '0', "julia");
        nodes[4] = node(1, '0', "julia");
        tree[1] = {2, 3};
        tree[3] = {4};
        cacheFieldTree2Functions(1, tree, nodes);
        for (unsigned seed = 1; seed <= 128; ++seed) {
            seedgen(seed);
            compareResolution(tree, nodes, sf::Vector2f(0.37f, -0.91f), 0.7);
        }
    }
}

} // namespace

int main() {
    try {
        runTests();
        std::cout << "Perlin cached dispatch preserves result bits and random state\n";
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
    return 0;
}
