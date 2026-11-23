"""One loop out of a generated clip: drops repeated frames (clips rendered "on twos",
still holds at the start), then keeps exactly one cycle (walk/run) or one action
(attack: from the last rest frame to the return to rest). Pure numpy, no models.
"""
import numpy as np


def small(frames, width=96):
    """Frames [N,H,W,3] in 0..1 -> [N,h,w,4] block-averaged thumbnails for comparison:
    the silhouette against the backdrop (border colour) weighs most, colour a little, so
    a backdrop or palette that drifts during the clip does not hide a returned pose."""
    n, h, w = frames.shape[:3]
    rgb = frames[..., :3]
    border = np.concatenate([rgb[:, :2].reshape(n, -1, 3), rgb[:, -2:].reshape(n, -1, 3),
                             rgb[:, :, :2].reshape(n, -1, 3), rgb[:, :, -2:].reshape(n, -1, 3)], axis=1)
    key = np.median(border, axis=1)[:, None, None, :]
    fg = (np.abs(rgb - key).max(axis=-1, keepdims=True) > 0.25).astype(np.float32)
    feat = np.concatenate([rgb * 0.25, fg], axis=-1)
    step = max(1, w // width)
    hh, ww = (h // step) * step, (w // step) * step
    f = feat[:, :hh, :ww].reshape(n, hh // step, step, ww // step, step, 4)
    return f.mean(axis=(2, 4))


def distances(thumbs):
    flat = thumbs.reshape(len(thumbs), -1).astype(np.float32)
    # Mean absolute difference between every pair of frames.
    # Считаем по одной строке: та же матрица, но без временного массива
    # (N, N, features) — на 124 кадрах это было 2.4 ГБ и падало при нехватке RAM.
    n = len(flat)
    out = np.empty((n, n), dtype=np.float32)
    for i in range(n):
        out[i] = np.abs(flat[i] - flat).mean(axis=1)
    return out


def unique_frames(thumbs, dup_share):
    """Every second frame when the clip is rendered "on twos" (each picture shown twice),
    otherwise all frames. Even spacing keeps the step smooth."""
    n = len(thumbs)
    d = np.abs(np.diff(thumbs.reshape(n, -1), axis=0)).mean(axis=1)
    if len(d) < 8:
        return list(range(n))
    # d[k] compares frames k and k+1; on twos one of the two phases is near zero.
    even, odd = np.median(d[0::2]), np.median(d[1::2])
    if min(even, odd) > max(even, odd) * dup_share:
        return list(range(n))
    # even small: frames 1,3,5... repeat 0,2,4... -> keep the even ones.
    return list(range(0, n, 2)) if even < odd else list(range(1, n, 2))


def find_cycle(D, min_len, max_len, close):
    """(start, length, seam) of the shortest clean loop: for every length the start whose
    frame `length` later matches it best; the first length where that match is a clean
    seam (a local best, within `close` of the clip's typical difference) is one cycle.
    Longer clean loops are two or three cycles of the same step."""
    m = len(D)
    far = float(np.percentile(D, 90)) or 1.0
    seams = []
    for p in range(min_len, min(max_len, m - 1) + 1):
        # Only starts whose loop really moves: a still hold also "returns" to itself.
        cands = [(D[i, i + p], i) for i in range(m - p) if D[i, i + 1:i + p].max() >= far * 0.5]
        if not cands:
            continue
        v, s = min(cands)
        seams.append((p, s, v / far))
    if not seams:
        return None
    for k, (p, s, v) in enumerate(seams):
        local = (k == 0 or v <= seams[k - 1][2]) and (k + 1 >= len(seams) or v <= seams[k + 1][2])
        if local and v <= close:
            return s, p, v
    return None


def find_action(D, rest_share):
    """(start, end) of the first action: from the last still frame before it to the moment
    it is back near the start pose, or stops moving away from the peak of the blow
    (later colour drift can keep a returned pose from matching the first frame exactly)."""
    m = len(D)
    d = np.array([D[i, i + 1] for i in range(m - 1)])
    if not len(d):
        return 0, m - 1
    still = max(float(np.percentile(d, 10)) * 3, 1e-6)
    moving = np.where(d > still)[0]
    if not len(moving):
        return 0, m - 1
    start = int(moving[0])
    base = D[start]
    run_max = 0.0
    for i in range(start + 1, m):
        run_max = max(run_max, float(base[i]))
        if i < start + 4:
            continue
        if base[i] <= run_max * rest_share:
            return start, i
        # Back near the start pose: a dip well below the peak of the blow.
        dip = i + 1 < m and base[i] <= base[i - 1] and base[i] <= base[i + 1]
        if dip and base[i] <= run_max * 0.3 and float(base[start + 1:i].max()) >= run_max * 0.99:
            return start, i
        stopped = d[i - 1] <= still and (i >= m - 1 or d[i] <= still)
        if stopped and base[i] < run_max * 0.6:
            return start, i
    return start, m - 1


def evenly(chosen, max_frames):
    """At most max_frames frames spread evenly over the loop (its end does not repeat its start)."""
    if max_frames <= 0 or len(chosen) <= max_frames:
        return chosen
    return [chosen[int(round(k * len(chosen) / max_frames))] for k in range(max_frames)]


def trim(frames, mode='cycle', dedupe=True, min_len=12, max_len=240, close=0.08, rest_share=0.15, dup_share=0.35, max_frames=0):
    chosen, info = _trim(frames, mode, dedupe, min_len, max_len, close, rest_share, dup_share)
    picked = evenly(chosen, max_frames)
    if len(picked) < len(chosen):
        info += ' -> %d frames' % len(picked)
    return picked, info


def _trim(frames, mode, dedupe, min_len, max_len, close, rest_share, dup_share):
    thumbs = small(frames)
    keep = unique_frames(thumbs, dup_share) if (dedupe and mode != 'keep') else list(range(len(frames)))
    D = distances(thumbs[keep])
    if mode == 'keep':
        chosen = keep
        info = 'keep: %d frames of %d' % (len(chosen), len(frames))
    elif mode == 'action':
        s, e = find_action(D, rest_share)
        chosen = keep[s:e + 1]
        info = 'action: frames %d-%d of %d (%d kept)' % (keep[s] + 1, keep[e] + 1, len(frames), len(chosen))
    else:
        found = find_cycle(D, min_len, max_len, close)
        if found is None:
            chosen = keep
            info = 'cycle: no loop found, %d unique frames of %d' % (len(keep), len(frames))
        else:
            s, p, score = found
            chosen = keep[s:s + p]
            info = 'cycle: frames %d-%d of %d, %d frames, seam %.0f%%' % (keep[s] + 1, keep[s + p] + 1, len(frames), len(chosen), score * 100)
    return chosen, info
