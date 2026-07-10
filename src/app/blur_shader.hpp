#pragma once

namespace pfb {
inline constexpr const char* kBlurShader = R"glsl(
uniform sampler2D texture;
uniform vec2 blur_radius;

void main() {
    vec2 uv = gl_TexCoord[0].xy;
    vec4 color = vec4(0.0);
    color += texture2D(texture, uv - 10.0 * blur_radius) * 0.0012;
    color += texture2D(texture, uv - 9.0 * blur_radius) * 0.0015;
    color += texture2D(texture, uv - 8.0 * blur_radius) * 0.0038;
    color += texture2D(texture, uv - 7.0 * blur_radius) * 0.0087;
    color += texture2D(texture, uv - 6.0 * blur_radius) * 0.0180;
    color += texture2D(texture, uv - 5.0 * blur_radius) * 0.0332;
    color += texture2D(texture, uv - 4.0 * blur_radius) * 0.0547;
    color += texture2D(texture, uv - 3.0 * blur_radius) * 0.0807;
    color += texture2D(texture, uv - 2.0 * blur_radius) * 0.1065;
    color += texture2D(texture, uv - blur_radius) * 0.1258;
    color += texture2D(texture, uv) * 0.1330;
    color += texture2D(texture, uv + blur_radius) * 0.1258;
    color += texture2D(texture, uv + 2.0 * blur_radius) * 0.1065;
    color += texture2D(texture, uv + 3.0 * blur_radius) * 0.0807;
    color += texture2D(texture, uv + 4.0 * blur_radius) * 0.0547;
    color += texture2D(texture, uv + 5.0 * blur_radius) * 0.0332;
    color += texture2D(texture, uv + 6.0 * blur_radius) * 0.0180;
    color += texture2D(texture, uv + 7.0 * blur_radius) * 0.0087;
    color += texture2D(texture, uv + 8.0 * blur_radius) * 0.0038;
    color += texture2D(texture, uv + 9.0 * blur_radius) * 0.0015;
    color += texture2D(texture, uv + 10.0 * blur_radius) * 0.0012;
    gl_FragColor = color;
}
)glsl";
}
