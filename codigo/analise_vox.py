"""Voxel-based occupancy of EVA-RT parts per height band (robust against non-watertight meshes)."""
import math, json, sys
import numpy as np, trimesh
from scipy import ndimage
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

M = 'EVA-RT/3d_models/'
P = 0.2


def occupancy(name, pitch=P):
    m = trimesh.load(M + name + '.stl')
    v = m.voxelized(pitch)
    try:
        v = v.fill()
    except Exception as e:
        print('fill failed', e)
    mat = v.matrix  # (nx, ny, nz) bool
    T = v.transform
    origin = T[:3, 3]
    return m, mat, origin, pitch


def band_mask(mat, origin, pitch, z0, z1):
    nz = mat.shape[2]
    zs = origin[2] + np.arange(nz) * pitch
    sel = (zs >= z0) & (zs <= z1)
    return mat[:, :, sel].any(axis=2) if sel.any() else np.zeros(mat.shape[:2], bool)


def extent(mask, origin, pitch):
    xs, ys = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (origin[0] + xs.min() * pitch, origin[1] + ys.min() * pitch, origin[0] + xs.max() * pitch, origin[1] + ys.max() * pitch)


if __name__ == '__main__':
    out = {}
    fig, axs = plt.subplots(2, 3, figsize=(18, 12))
    # ---- impeller base: robot frame = STL rotated +45 deg (legs on diagonals) ----
    m, mat, o, p = occupancy('impeller_base_1')
    print('impeller voxels', mat.shape, 'origin', o.round(2))
    ax = axs[0, 0]
    cols = {(0, 1.0): 'Reds', (1.0, 6.0): 'Oranges', (6.0, 11.0): 'Greens', (11.0, 12.0): 'Blues', (12.0, 14.2): 'Purples'}
    for (z0, z1), cm in cols.items():
        mk = band_mask(mat, o, p, z0, z1)
        ex = extent(mk, o, p)
        lab, n = ndimage.label(mk)
        print(f'  band z {z0}-{z1}: {n} parts, extent {None if ex is None else [round(e, 1) for e in ex]}')
        # polar stats per part (in STL frame)
        for k in range(1, n + 1):
            xs, ys = np.nonzero(lab == k)
            X = o[0] + xs * p; Y = o[1] + ys * p
            r = np.hypot(X, Y); a = np.degrees(np.arctan2(Y, X))
            if len(X) < 5: continue
            print(f'     part{k}: n={len(X)} area={len(X)*p*p:.0f} r {r.min():.1f}-{r.max():.1f} ang {a.min():.0f}..{a.max():.0f} c=({X.mean():.1f},{Y.mean():.1f})')
        ax.imshow(np.ma.masked_where(~mk.T, mk.T), origin='lower', cmap=cm, alpha=0.5, vmin=0, vmax=1.3,
                  extent=[o[0], o[0] + mat.shape[0] * p, o[1], o[1] + mat.shape[1] * p])
        out[f'imp_{z0}_{z1}'] = dict(mask=mk.tolist(), origin=o.tolist(), pitch=p)
    ax.set_title('impeller_base_1 (frame do STL): vermelho z<1, laranja 1-6, verde 6-11, azul 11-12, roxo >12')
    ax.set_aspect('equal'); ax.grid(lw=0.3)

    # ---- suction base ----
    m, mat, o, p = occupancy('suction_base')
    mk = band_mask(mat, o, p, -1, 1)
    print('suction extent', [round(e, 2) for e in extent(mk, o, p)], 'area', mk.sum() * p * p)
    holes = ndimage.label(~mk)[0]
    print('  suction: free regions (label count)', holes.max())
    for k in range(1, holes.max() + 1):
        xs, ys = np.nonzero(holes == k)
        if len(xs) < 3: continue
        X = o[0] + xs * p; Y = o[1] + ys * p
        print(f'    free{k}: area {len(xs)*p*p:.1f} x {X.min():.1f}..{X.max():.1f} y {Y.min():.1f}..{Y.max():.1f}')
    ax = axs[0, 1]
    ax.imshow(mk.T, origin='lower', cmap='Greens', extent=[o[0], o[0] + mat.shape[0] * p, o[1], o[1] + mat.shape[1] * p])
    ax.set_title('suction_base (frame do STL)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
    out['suction'] = dict(mask=mk.tolist(), origin=o.tolist(), pitch=p)

    # ---- gearbox ----
    m, mat, o, p = occupancy('gearbox')
    for z0, z1 in [(-2.6, -0.05), (0.0, 0.5), (0.5, 3.0), (3.0, 12)]:
        mk = band_mask(mat, o, p, z0, z1)
        print(f'gearbox band {z0}-{z1}: extent {extent(mk, o, p)} area {mk.sum()*p*p:.0f}')
    # side view: occupancy projected along x -> (y,z)
    side = mat.any(axis=0)
    ax = axs[0, 2]
    ax.imshow(side.T, origin='lower', cmap='Greys', extent=[o[1], o[1] + mat.shape[1] * p, o[2], o[2] + mat.shape[2] * p])
    ax.set_title('gearbox vista lateral (y,z)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
    # find bores: in the xz-plane sections, look for empty circular regions -> look at projection along y of "empty inside bbox"
    front = mat.any(axis=1)
    ax = axs[1, 0]
    ax.imshow(front.T, origin='lower', cmap='Greys', extent=[o[0], o[0] + mat.shape[0] * p, o[2], o[2] + mat.shape[2] * p])
    ax.set_title('gearbox vista frontal (x,z)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
    # slices at several y to find bore circles (holes in the (x,z) slice)
    ny = mat.shape[1]
    for j in range(0, ny, max(1, ny // 14)):
        sl = mat[:, j, :]
        lab, n = ndimage.label(~sl)
        # holes = background regions not touching the border
        border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
        hs = []
        for k in range(1, n + 1):
            if k in border: continue
            xs, zs = np.nonzero(lab == k)
            if len(xs) < 8: continue
            hs.append((round(o[0] + xs.mean() * p, 2), round(o[2] + zs.mean() * p, 2), round(2 * math.sqrt(len(xs) * p * p / math.pi), 2)))
        if hs:
            print(f'  gearbox slice y={o[1] + j * p:6.2f}: holes (x,z,dEq) {hs}')

    # ---- wheel rim ----
    m, mat, o, p = occupancy('wheel_rim')
    print('wheel_rim extent', m.bounds.round(2).tolist())
    # ---- clamp / sledge / battery holder ----
    for nm, ax in [('barilla_clamp', axs[1, 1]), ('sensor_sledge', axs[1, 2])]:
        m, mat, o, p = occupancy(nm)
        top = mat.any(axis=2)
        ax.imshow(top.T, origin='lower', cmap='Greys', extent=[o[0], o[0] + mat.shape[0] * p, o[1], o[1] + mat.shape[1] * p])
        ax.plot(0, 0, 'r+', ms=12)
        ax.set_title(nm + ' (vista de cima, + = origem)'); ax.set_aspect('equal'); ax.grid(lw=0.3)
        print(nm, 'bounds', m.bounds.round(2).tolist())
    fig.tight_layout(); fig.savefig('stl_vox.png', dpi=75)
    json.dump({k: v for k, v in out.items()}, open('vox_geom.json', 'w'))
