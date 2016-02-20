"""

RenderPipeline

Copyright (c) 2014-2016 tobspr <tobias.springer1@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

"""
from __future__ import division

from panda3d.core import PTAInt, Vec4

from rpcore.render_stage import RenderStage

class SMAAStage(RenderStage):

    """ This stage does the actual SMAA """

    required_pipes = ["ShadedScene", "GBuffer"]
    required_inputs = []

    def __init__(self, pipeline):
        RenderStage.__init__(self, "SMAAStage", pipeline)
        self.area_tex = None
        self.search_tex = None
        self.use_reprojection = True
        self._jitter_index = PTAInt.empty_array(1)

    def set_jitter_index(self, idx):
        """ Sets the current jitter index """
        self._jitter_index[0] = idx
        self._neighbor_targets[0].set_active(idx == 0)
        self._neighbor_targets[1].set_active(idx == 1)
        self._resolve_target.set_shader_input("CurrentTex", self._neighbor_targets[idx]["color"])
        self._resolve_target.set_shader_input("LastTex", self._neighbor_targets[1-idx]["color"])

    @property
    def produced_pipes(self):
        if self.use_reprojection:
            return {"ShadedScene": self._resolve_target["color"]}
        else:
            return {"ShadedScene": self._neighbor_targets[0]["color"]}

    def create(self):
        # Edge detection
        self._edge_target = self.make_target("EdgeDetection")
        self._edge_target.add_color_texture()
        self._edge_target.prepare_offscreen_buffer()
        self._edge_target.set_clear_color(color=Vec4(0))

        # Weight blending
        self._blend_target = self.make_target("BlendWeights")
        self._blend_target.add_color_texture()
        self._blend_target.has_color_alpha = True
        self._blend_target.prepare_offscreen_buffer()
        self._blend_target.set_clear_color(color=Vec4(0))

        self._blend_target.set_shader_input("EdgeTex", self._edge_target["color"])
        self._blend_target.set_shader_input("AreaTex", self.area_tex)
        self._blend_target.set_shader_input("SearchTex", self.search_tex)
        self._blend_target.set_shader_input("JitterIndex", self._jitter_index)

        # Neighbor blending
        self._neighbor_targets = []
        for i in range(2 if self.use_reprojection else 1):

            target = self.make_target("Neighbor-" + str(i))
            target.add_color_texture(bits=16)
            target.prepare_offscreen_buffer()
            target.set_shader_input("BlendTex", self._blend_target["color"])
            self._neighbor_targets.append(target)

        # Resolving
        if self.use_reprojection:
            self._resolve_target = self.make_target("Resolve")
            self._resolve_target.add_color_texture(bits=16)
            self._resolve_target.prepare_offscreen_buffer()
            self._resolve_target.set_shader_input("JitterIndex", self._jitter_index)

            # Set initial textures
            self._resolve_target.set_shader_input("CurrentTex", self._neighbor_targets[0]["color"])
            self._resolve_target.set_shader_input("LastTex", self._neighbor_targets[1]["color"])

    def set_shaders(self):
        self._edge_target.set_shader(self.load_plugin_shader("edge_detection.frag.glsl"))
        self._blend_target.set_shader(self.load_plugin_shader("blending_weights.frag.glsl"))
        for target in self._neighbor_targets:
            target.set_shader(self.load_plugin_shader("neighborhood_blending.frag.glsl"))

        if self.use_reprojection:
            self._resolve_target.set_shader(self.load_plugin_shader("resolve.frag.glsl"))
