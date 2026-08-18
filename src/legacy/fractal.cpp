#define WINDOW
#define OUTPUT

#include "aural.hpp"
#include "../app/blur_shader.hpp"
#include <iostream>

using namespace au;
using namespace au::app;
using namespace au::math;
using namespace au::rnd;
using namespace au::flame;

const std::string version = "1.0.0";

vec affinePost(vec v, const std::vector<double>& c) {
    //rotating, shear, scale disabled
    return vec(v.x+c[1], v.y+c[2]);
}

vec affine(vec v, const std::vector<double>& c) {
    return vec(v.x*c[0]+v.y*c[1]+c[2], v.x*c[3]+v.y*c[4]+c[5]);
}

class baseApp : public App {
    using App::App;
    public:
        struct func {
            std::vector<std::string> id;
            std::vector<double> w, c, p;
            sf::Color col;
            double mult;

            func(std::vector<std::string> id, std::vector<double> w, std::vector<double> c, sf::Color col, std::vector<double> p, double mult) : id(id), w(w), c(c), col(col), p(p), mult(mult) {}
            func() {

            }
        };

        sf::Shader blur;
        bool blur_loaded = false;
        sf::VertexArray pointBatch{sf::Quads};

        struct fractal {
            vec v, initial_v;
            sf::Color c;
            std::vector<func> funcs;
            std::vector<double> weights, final_p;
            std::vector<std::string> available_vars;
            std::vector<std::vector<double> > backup_pcoeffs, backup_coeffs;
            double zoom = 1;
            int final_func;
            int hue;
            int rotations = 0;

            fractal(int hue, const std::vector<std::string>& available_vars) : hue(hue), available_vars(available_vars) {}
            fractal() {
                hue = random(0, 360);
                int diffs = random(3, 7);
                while(diffs--) {
                    available_vars.push_back(randVariation());
                }
            }

            void randomiseCoeffs(double t) {
                zoom = constrain(abs(noise(t)*10), 1, 10);
                for(std::size_t i = 0; i < funcs.size(); i++)
                    for(int j = 0; j < 6; j++)
                        funcs[i].p[j] = constrain(backup_pcoeffs[i][j]*noise(t+j*100+i*100)*5, -1.0, 1.0),
                        funcs[i].c[j] = constrain(backup_coeffs[i][j]*noise(t+j*1000+i*1000)*10, -1.0, 1.0);

                for(int i = 0; i < 6; i++)
                    final_p[i] = constrain(backup_pcoeffs[funcs.size()][i]*noise(t+i*100), -1.0, 1.0);
            }

            vec rotatePoint(vec v, double angle, vec center) {
                v = v-center;
                double xnew = v.x*cos(angle)-v.y*sin(angle);
                double ynew = v.x*sin(angle)+v.y*cos(angle);
                return vec(xnew+center.x, ynew+center.y);
            }

            int weightedRand() {
                double r = random(1.0), w = 0;
                for(std::size_t i = 0; i < weights.size(); i++) {
                    w += weights[i];
                    if(r <= w) return static_cast<int>(i);
                }
                return 0;
            }

            vec runFunc(vec v, int fi) {
                vec ret(0, 0);
                const auto& f = funcs[fi];

                flame::A = f.c[0];
                flame::B = f.c[1];
                flame::C = f.c[2];
                flame::D = f.c[3];
                flame::B = f.c[4];
                flame::B = f.c[5];

                const vec affineV = affine(v, f.c);
                for(std::size_t i = 0; i < f.id.size(); i++) {
                    vec s = variations[f.id[i]](affineV, f.w[i]);
                    ret = ret + s;
                }
                ret = affinePost(ret, f.p);
                return ret;
            }

            void initialize(double t) {
                v = initial_v = vec(random(-1.0, 1.0), random(-1.0, 1.0));
                c = convert(Hsv(hue, 0.85, 0.85));
                if(random(0, 100) < 10) rotations = random(1, 5);

                int func_number = random(3, 8);
                funcs.reserve(static_cast<std::size_t>(func_number + 1));
                weights.reserve(static_cast<std::size_t>(func_number));
                backup_pcoeffs.reserve(static_cast<std::size_t>(func_number + 2));
                backup_coeffs.reserve(static_cast<std::size_t>(func_number + 1));
                final_p.reserve(6);

                for(int i = 1; i <= func_number+1; i++) {
                    if(i <= func_number) weights.push_back(0);
                    std::vector<std::string> id;
                    std::vector<double> w, c, p;
                    sf::Color col;

                    int vars = random(3, 10);
                    id.reserve(static_cast<std::size_t>(vars));
                    w.reserve(static_cast<std::size_t>(vars));
                    c.reserve(6);
                    p.reserve(6);

                    for(int i = 1; i <= vars; i++) {
                        auto temp = available_vars[random(0, available_vars.size()-1)];
                        bool valid = 1;
                        for(const auto& test : id) if(test == temp) valid = 0;
                        if(valid)
                            id.push_back(temp),
                            w.push_back(0);
                    }

                    double w_sum = 0, w_inc = 0.05;
                    while(w_sum < 1) {
                        w[random(0, id.size()-1)] += w_inc;
                        w_sum += w_inc;
                    }

                    int temp_hue = (hue+random(0, 40))%360;
                    if(random(0, 100) < 30) temp_hue = (hue+random(160, 200))%360;
                    col = convert(Hsv(temp_hue, random(0.7, 0.9), random(0.7, 0.9)));

                    for(int j = 0; j < 6; j++)
                        c.push_back(random(-1.5, 1.5)),
                        p.push_back(constrain((t+j*100)*5, -1.0, 1.0));
                    backup_pcoeffs.push_back(p);
                    backup_coeffs.push_back(c);

                    funcs.push_back(func(id, w, c, col, p, 1));
                }

                double f_sum = 0, f_inc = 0.5;
                while(f_sum < 0.99) {
                    weights[random(0, func_number-1)] += f_inc;
                    f_sum += f_inc;
                    f_inc /= 2;
                }

                final_func = func_number;
                for(int j = 0; j < 6; j++)
                    final_p.push_back(constrain((t+j*100)*5, -1.0, 1.0));
                backup_pcoeffs.push_back(final_p);
            }
        };

        virtual void init() {
            #ifdef WINDOW
            initWindow();
            #endif
            texture.create(screen_width, screen_height);
            texture.setSmooth(true);
            clock.restart();
            seed = std::chrono::system_clock::now().time_since_epoch().count();
        }

        std::vector<fractal> fractals;
        int fractal_number = 6, hue = 0, hue_override = -1;

        void setup() {
            blur_loaded = blur.loadFromMemory(pfb::kBlurShader, sf::Shader::Fragment);
            #ifdef WINDOW
            sf::ContextSettings settings;
            settings.antialiasingLevel = 8;
            window.create(sf::VideoMode(screen_width, screen_height), window_name, sf::Style::Close, settings);
            window.setVerticalSyncEnabled(true);
            window.setFramerateLimit(60);
            #endif

            timeLimit = 40;
            save_path = "./";

            clear(sf::Color(5, 5, 5));

            hue = (hue_override >= 0) ? hue_override : random(0, 360);

            int diffs = random(4, 12);
            std::vector<std::string> vars;
            vars.reserve(static_cast<std::size_t>(diffs));
            while(diffs--)
                vars.push_back(randVariation());

            fractal_number = random(3, 7);
            double temp_seed = random(1.0, 1000.0);
            fractals.reserve(static_cast<std::size_t>(fractal_number));

            for(int i = 1; i <= fractal_number; i++) {
                int temp_hue = (hue+random(0, 20))%360;
                if(random(0, 100) < 20) temp_hue = (hue+random(160, 200))%360;
                fractals.push_back(fractal(temp_hue, vars));
                fractals.back().initialize(temp_seed);
            }
        }

        bool preprocess = 1, blur_pass = 1;
        int hits[2100][2100], cur_it = 1;
        double t = 0, t_max;
        double preprocess_time = 8, max_hits = 0, temp_hits = 0;

        void loop() {
            #ifdef WINDOW
            checkForEvents();
            #endif

            if(preprocess) {
                t += 5;

                for(auto &f : fractals) {
                    f.v = f.initial_v;
                    f.randomiseCoeffs(t);
                }

                clear(sf::Color(5, 5, 5));
                temp_hits = 0, cur_it = t;
            }

            if(blur_pass && clock.getElapsedTime().asSeconds() >= 20) {
                blur_pass = 0;

                sf::Texture orig(texture.getTexture());

                sf::RenderStates states;
                states.blendMode = sf::BlendMultiply;
                texture.draw(sf::Sprite(orig), states);

                sf::Texture mult(texture.getTexture());
                texture.draw(sf::Sprite(orig));

                states.shader = &blur;
                states.blendMode = sf::BlendAdd;

                // Noise to remove banding. Preserve the legacy inclusive loops
                // (and therefore every RNG call) but upload/draw the in-bounds
                // pixels in one operation instead of millions of rectangles.
                sf::Color c = convert(Hsv((hue+random(0, 40))%360, 0.85, 2.8*random(0.03, 0.045)));
                sf::Image noiseImage;
                noiseImage.create(static_cast<unsigned int>(screen_width),
                                  static_cast<unsigned int>(screen_height),
                                  sf::Color::Transparent);

                for(int i = 0; i <= screen_width; i++) {
                    for(int j = 0; j <= screen_height; j++) {
                        c.a = constrain(gaussian(90, 40), 1, 255);
                        if(i < screen_width && j < screen_height)
                            noiseImage.setPixel(static_cast<unsigned int>(i),
                                                static_cast<unsigned int>(j), c);
                    }
                }

                sf::Texture noiseTexture;
                if(noiseTexture.loadFromImage(noiseImage))
                    texture.draw(sf::Sprite(noiseTexture));

                // bloom
                blur.setUniform("blur_radius", sf::Vector2f(-0.001, 0.001));
                texture.draw(sf::Sprite(mult), states);
                blur.setUniform("blur_radius", sf::Vector2f(0.001, 0.001));
                texture.draw(sf::Sprite(mult), states);

                for(auto &f : fractals) {
                    f.v = f.initial_v;
                    f.randomiseCoeffs(t_max);
                }

                texture.display();
            }

            if(preprocess && clock.getElapsedTime().asSeconds() >= preprocess_time) {
                for(auto &f : fractals) {
                    f.v = f.initial_v;
                    f.randomiseCoeffs(t_max);
                }

                preprocess = 0;

                clear(sf::Color(5, 5, 5));

                sf::Vertex background[] = {
                    sf::Vertex(sf::Vector2f(0, 0), convert(Hsv((hue+(random(0, 100) < 25 ? random(160, 200) : random(0, 40)))%360, 0.9, 2.8*random(0.02, 0.045)))),
                    sf::Vertex(sf::Vector2f(screen_width, 0), convert(Hsv((hue+(random(0, 100) < 25 ? random(160, 200) : random(0, 40)))%360, 0.9, 2.8*random(0.02, 0.045)))),
                    sf::Vertex(sf::Vector2f(screen_width, screen_height), convert(Hsv((hue+(random(0, 100) < 25 ? random(160, 200) : random(0, 40)))%360, 0.9, 2.8*random(0.02, 0.045)))),
                    sf::Vertex(sf::Vector2f(0, screen_height), convert(Hsv((hue+(random(0, 100) < 25 ? random(160, 200) : random(0, 40)))%360, 0.9, 2.8*random(0.02, 0.045))))
                };

                texture.draw(background, 4, sf::Quads);
            }

            pointBatch.resize(fractals.size() * static_cast<std::size_t>(2980 * 4));
            std::size_t vertexIndex = 0;

            for(auto &f : fractals) {
                double cur_rot = 0;
                for(int it = 1; it <= 3000; it++) {
                    int i = f.weightedRand();
                    f.v = f.runFunc(f.v, i);
                    f.v = f.runFunc(f.v, f.final_func);

                    f.v = affinePost(f.v, f.final_p);
                    f.c = interpolate(f.c, f.funcs[i].col, 0.5);
                    f.c = interpolate(f.c, f.funcs[f.final_func].col, 0.5);
                    vec vz = f.v*f.zoom;

                    if(it > 20) {
                        int fx = (vz.x+1)*600;
                        int fy = (vz.y+1)*600;

                        if(f.rotations > 1) {
                            vec point = vz;
                            point = f.rotatePoint(point, cur_rot, affine(vec(0, 0), f.final_p));
                            cur_rot = fmod(cur_rot + (2*M_PI/f.rotations), 2*M_PI);
                            fx = (point.x+1)*600;
                            fy = (point.y+1)*600;
                        }

                        f.c.a = (preprocess ? 255 : 30);
                        if(fx > 0 && fx < 2000 && fy > 0 && fy < 2000) {
                            if(preprocess && hits[fx][fy] != cur_it) {
                                hits[fx][fy] = cur_it;
                                temp_hits++;
                            }
                            const float left = static_cast<float>(fx);
                            const float top = static_cast<float>(fy);
                            pointBatch[vertexIndex++] = sf::Vertex(sf::Vector2f(left, top), f.c);
                            pointBatch[vertexIndex++] = sf::Vertex(sf::Vector2f(left + 1.f, top), f.c);
                            pointBatch[vertexIndex++] = sf::Vertex(sf::Vector2f(left + 1.f, top + 1.f), f.c);
                            pointBatch[vertexIndex++] = sf::Vertex(sf::Vector2f(left, top + 1.f), f.c);
                        }
                    }
                }
            }

            pointBatch.resize(vertexIndex);
            if(vertexIndex != 0) texture.draw(pointBatch, sf::BlendAdd);
            texture.display();

            if(preprocess && temp_hits > max_hits) {
                max_hits = temp_hits;
                t_max = t;
            }

            #ifdef WINDOW
            drawTextureToWindow();
            #endif
        }
        void close() {
            #ifdef WINDOW
            if(window.isOpen()) window.close();
            #endif
            #ifdef OUTPUT
            std::string info = saveFile() + "#method=fractal flame";
            info+="#seed="+std::to_string(seed)+"/"+version;
            std::cout << info;
            #else
            saveFile();
            #endif
        }
};

baseApp& pfbFractalApp() {
    static baseApp value(2000, 2000);
    return value;
}
#define testApp (pfbFractalApp())

AURAL_APP(testApp)
