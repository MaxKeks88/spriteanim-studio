"""Local ComfyUI chroma key for opaque illustrated sprites. No model downloads.

Works one frame at a time on CPU to bound temporary memory at 1024px video sizes.
IMAGE output is straight-alpha RGBA. Foreground mask: 1 = opaque subject.
"""
import numpy as np
import torch
from scipy import ndimage


def key_frame(rgb, key_color, sample_border, clip_black, clip_white,
              despill, choke_px, edge_bleed_px):
    rgb = np.asarray(rgb, dtype=np.float32)[..., :3]
    presets = {'magenta': (1., 0., 1.), 'green': (0., 1., 0.), 'blue': (0., 0., 1.)}
    bg = np.array(presets.get(key_color, presets['magenta']), dtype=np.float32)
    distance_mode = False
    if sample_border:
        # Sampling the outermost strips avoids the subject on this full-body canvas.
        border = np.concatenate((rgb[:3].reshape(-1,3), rgb[-3:].reshape(-1,3),
                                 rgb[:, :3].reshape(-1,3), rgb[:, -3:].reshape(-1,3)))
        measured = np.median(border, axis=0).astype(np.float32)
        close = np.linalg.norm(border - measured, axis=1) <= .12
        flat = float(close.mean()) if close.size else 0.
        if flat >= .55:
            # The model may paint a different flat color than requested. Use the
            # actual border color and a distance matte so any flat backdrop works
            # and a per-frame color flicker is still keyed cleanly.
            bg = measured
            distance_mode = True
        elif signal(measured, key_color) > .15:
            bg = measured
    if distance_mode:
        dist = np.linalg.norm(rgb - bg, axis=-1) / float(np.sqrt(3.))
        raw_alpha = np.clip((dist - .09) / .26, 0., 1.)
    else:
        raw_alpha = np.clip(1. - signal(rgb, key_color) / max(float(signal(bg, key_color)), .05), 0., 1.)
    alpha = np.clip((raw_alpha - clip_black) / max(clip_white - clip_black, .001), 0., 1.)
    if choke_px > 0:
        whole = int(choke_px)
        if whole:
            alpha = ndimage.minimum_filter(alpha, size=whole * 2 + 1, mode='nearest')
        fraction = choke_px - whole
        if fraction:
            alpha = alpha * (1. - fraction) + ndimage.minimum_filter(alpha, size=3, mode='nearest') * fraction
    # Unmix background only on partially transparent edges. Opaque interiors stay intact.
    recovered = np.clip((rgb - (1. - raw_alpha[...,None]) * bg) / np.maximum(raw_alpha[...,None], .02), 0., 1.)
    edge = ((raw_alpha > clip_black) & (raw_alpha < clip_white))[...,None]
    foreground = np.where(edge, rgb * (1. - despill) + recovered * despill, rgb).astype(np.float32)
    if edge_bleed_px > 0:
        solid = alpha >= .5
        if solid.any():
            distance, indices = ndimage.distance_transform_edt(~solid, return_indices=True)
            extend = (alpha < .01) & (distance <= edge_bleed_px)
            foreground[extend] = foreground[indices[0][extend], indices[1][extend]]
    return np.concatenate((foreground, alpha[...,None]), axis=-1)


def signal(rgb, key):
    r,g,b = rgb[...,0],rgb[...,1],rgb[...,2]
    if key == 'magenta': return np.minimum(r,b) - g
    if key == 'green': return g - np.maximum(r,b)
    return b - np.maximum(r,g)


class SpriteChromaKey:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'images': ('IMAGE',),
            'key_color': (['magenta','green','blue'], {'default':'magenta'}),
            'sample_border': ('BOOLEAN', {'default':True, 'tooltip':'Estimate the actual backdrop color from each frame border. Works for any flat color, so a wrong or flickering backdrop is still keyed; the subject must not touch the border.'}),
            'clip_black': ('FLOAT', {'default':.04, 'min':0., 'max':.4, 'step':.01, 'tooltip':'Raise to clear faint background haze. Too high removes thin details.'}),
            'clip_white': ('FLOAT', {'default':.97, 'min':.5, 'max':1., 'step':.01, 'tooltip':'Lower to make more of the subject fully opaque.'}),
            'despill': ('FLOAT', {'default':1., 'min':0., 'max':1., 'step':.05, 'tooltip':'Remove backdrop color mixed into partially transparent edges.'}),
            'choke_px': ('FLOAT', {'default':0., 'min':0., 'max':3., 'step':.1, 'tooltip':'Shrink matte in source pixels. Try 0.2-0.5 only if a fringe remains; excessive shrink cuts outlines.'}),
            'edge_bleed_px': ('INT', {'default':4, 'min':0, 'max':16, 'step':1, 'tooltip':'Extend foreground RGB under transparent pixels to reduce filtering fringes.'}),
        }}
    RETURN_TYPES = ('IMAGE','MASK')
    RETURN_NAMES = ('rgba_straight','foreground_mask')
    FUNCTION = 'execute'
    CATEGORY = 'Sprite / Background'
    DESCRIPTION = 'Chroma key with edge color unmixing. Saves true RGBA through SaveImage. For solid characters over a clear colored backdrop; not a general AI segmenter.'

    def execute(self, images, key_color='magenta', sample_border=True, clip_black=.04,
                clip_white=.97, despill=1., choke_px=0., edge_bleed_px=4):
        if clip_white <= clip_black:
            raise ValueError('clip_white must be greater than clip_black')
        from comfy.utils import ProgressBar
        progress = ProgressBar(len(images))
        result = torch.empty((*images.shape[:3],4), dtype=torch.float32, device='cpu')
        for i in range(len(images)):
            result[i] = torch.from_numpy(key_frame(images[i].detach().cpu().numpy(), key_color,
                sample_border, clip_black, clip_white, despill, choke_px, edge_bleed_px))
            progress.update(1)
        return result, result[...,3]


class SpriteLoopTrim:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'images': ('IMAGE',),
            'mode': (['cycle', 'action'], {'default': 'cycle', 'tooltip': 'cycle: one walk/run loop (its last frame leads back into the first). action: one attack, from the last rest frame to the return to rest.'}),
            'max_frames': ('INT', {'default': 0, 'min': 0, 'max': 512, 'step': 1, 'tooltip': '0 = every frame of the loop. Otherwise at most this many frames, spread evenly over the loop.'}),
            'dedupe_twos': ('BOOLEAN', {'default': True, 'tooltip': 'Clips rendered "on twos" show every picture twice: keep every second frame.'}),
            'min_frames': ('INT', {'default': 12, 'min': 3, 'max': 256, 'step': 1, 'tooltip': 'Shortest loop to accept (cycle mode).'}),
        }}
    RETURN_TYPES = ('IMAGE', 'INT', 'STRING')
    RETURN_NAMES = ('images', 'frame_count', 'info')
    FUNCTION = 'execute'
    CATEGORY = 'Sprite / Animation'
    DESCRIPTION = 'Keeps exactly one loop of a generated clip: one walk/run cycle or one attack. Repeated frames are dropped first.'

    def execute(self, images, mode='cycle', max_frames=0, dedupe_twos=True, min_frames=12):
        from . import loop_trim
        frames = images.detach().cpu().numpy()
        chosen, info = loop_trim.trim(frames, mode, dedupe=dedupe_twos, min_len=min_frames, max_frames=max_frames)
        print('[SpriteLoopTrim] ' + info)
        return images[chosen], len(chosen), info


NODE_CLASS_MAPPINGS = {'SpriteChromaKey': SpriteChromaKey, 'SpriteLoopTrim': SpriteLoopTrim}
NODE_DISPLAY_NAME_MAPPINGS = {'SpriteChromaKey': 'Sprite: Remove Background + Edge Cleanup',
                              'SpriteLoopTrim': 'Sprite: Keep One Loop'}
