"""One routing cycle: export DSN -> Freerouting -> import SES -> vector DRC + connectivity -> render."""
import subprocess, sys, os, pickle, re, time
import dsn_io, drc_v3

HERE = os.path.dirname(os.path.abspath(__file__))
FR = os.path.join(HERE, 'fr')


def run(tag, widths=None, skip=('GND',), passes=150, neck=False, extra_args=(), render=True, seed_ses=None, seed_protect=False, gnd_top_center=None, shuffle_seed=None, layer_cost=None):
    widths = widths or {'sinal': 0.8, 'power': 1.2, 'p3v3': 0.9}
    dsn = os.path.join(FR, f'{tag}.dsn'); ses = os.path.join(FR, f'{tag}.ses')
    dsn_io.export(dsn, widths=widths, skip_nets=skip, seed_ses=seed_ses, seed_protect=seed_protect, gnd_top_center=gnd_top_center, shuffle_seed=shuffle_seed, layer_cost=layer_cost)
    if os.path.exists(ses):
        os.remove(ses)
    cmd = ['java', '-Djava.awt.headless=true', f'-Duser.home={FR}/home', '-jar', f'{FR}/freerouting.jar',
           '-de', dsn, '-do', ses] + (['-dr', dsn.replace('.dsn', '.rules')] if layer_cost else []) + [ '-mp', str(passes), '-mt', '6', '--gui.enabled=false',
           f'--router.automatic_neckdown={"true" if neck else "false"}', '--router.copper_to_edge_clearance_um=650'] + list(extra_args)
    env = dict(os.environ, HOME=f'{FR}/home')
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
    m = re.findall(r'final score: [0-9.]+ \(([0-9]+) unrouted and ([0-9]+) violations\)', p.stdout + p.stderr)
    fr_unr, fr_vio = (m[-1] if m else ('?', '?'))
    tracks, vias = dsn_io.import_ses(ses)
    R = dict(tracks=tracks, vias=vias, failed=[], extra={})
    pickle.dump(R, open(os.path.join(HERE, f'route_{tag}.pkl'), 'wb'))
    R2, C, nets = drc_v3.load(tag)
    for n in skip:
        nets.pop(n, None)
    errs, disc, cu = drc_v3.drc(R2, C, nets, verbose=False)
    nv = sum(len(v) for v in vias.values())
    print(f'[{tag}] FR: {fr_unr} sem rota, {fr_vio} violacoes | meu DRC: {len(errs)} | redes abertas: {len(disc)} | vias: {nv} | {time.time()-t0:.0f}s')
    for n, g in disc:
        print(f'     aberta {n}: {g}')
    for e in errs[:12]:
        print('     drc', e)
    if render:
        fn = f'/projects/sandbox/ver_{tag}.png'
        drc_v3.render(R2, C, nets, fn, f'{tag}: {len(disc)} redes abertas, {nv} vias')
    return errs, disc, R2, C, nets


if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else 'ciclo')
