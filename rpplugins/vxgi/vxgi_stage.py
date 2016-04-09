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

from panda3d.core import LVecBase2i, Vec2

from rpcore.render_stage import RenderStage
from rpcore.stages.ambient_stage import AmbientStage

class VXGIStage(RenderStage):

    required_inputs = ["voxelGridPosition"]
    required_pipes = ["ShadedScene", "SceneVoxels", "GBuffer", "ScatteringIBLSpecular",
                      "ScatteringIBLDiffuse"]

    @property
    def produced_pipes(self):
        return {
            "VXGISpecular": self._target_spec.color_tex,
            "VXGIDiffuse": self._target_upscale_diff.color_tex
        }

    def create(self):
        # Create a target for the specular GI
        self._target_spec = self.create_target("SpecularGI")
        self._target_spec.add_color_attachment(bits=16, alpha=True)
        self._target_spec.prepare_buffer()

        # Create a target for the diffuse GI
        self._target_diff = self.create_target("DiffuseGI")
        self._target_diff.size = -2
        self._target_diff.add_color_attachment(bits=16)
        self._target_diff.prepare_buffer()

        # Create the target which blurs the diffuse result
        self._target_blur_v = self.create_target("BlurV")
        self._target_blur_v.size = -2
        self._target_blur_v.add_color_attachment(bits=16)
        self._target_blur_v.has_color_alpha = True
        self._target_blur_v.prepare_buffer()
        self._target_blur_v.set_shader_input("SourceTex", self._target_diff.color_tex)

        self._target_blur_h = self.create_target("BlurH")
        self._target_blur_h.size = -2
        self._target_blur_h.add_color_attachment(bits=16)
        self._target_blur_h.has_color_alpha = True
        self._target_blur_h.prepare_buffer()
        self._target_blur_h.set_shader_input("SourceTex", self._target_blur_v.color_tex)

       # Create the target which bilateral upsamples the diffuse target
        self._target_upscale_diff = self.create_target("UpscaleDiffuse")
        self._target_upscale_diff.add_color_attachment(bits=16)
        self._target_upscale_diff.prepare_buffer()
        self._target_upscale_diff.set_shader_input("SourceTex", self._target_blur_h.color_tex)
        self._target_upscale_diff.set_shader_input("upscaleWeights", Vec2(0.0001, 0.001))
        self._target_upscale_diff.set_shader_input("useZAsWeight", False)

        # Set blur parameters
        self._target_blur_v.set_shader_input("blur_direction", LVecBase2i(0, 1))
        self._target_blur_h.set_shader_input("blur_direction", LVecBase2i(1, 0))

        # Make the ambient stage use the GI result
        AmbientStage.required_pipes += ["VXGISpecular", "VXGIDiffuse"]

    def reload_shaders(self):
        self._target_spec.shader = self.load_plugin_shader("vxgi_specular.frag.glsl")
        self._target_diff.shader = self.load_plugin_shader("vxgi_diffuse.frag.glsl")
        self._target_upscale_diff.shader = self.load_plugin_shader(
            "/$$rp/shader/bilateral_upscale.frag.glsl")
        blur_shader = self.load_plugin_shader(
            "/$$rp/shader/bilateral_halfres_blur.frag.glsl")
        self._target_blur_v.shader = blur_shader
        self._target_blur_h.shader = blur_shader
