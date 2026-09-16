# -*- coding: utf-8 -*-
"""Constroi o dataset nacional: concelhos + farmacias + metricas de transferencia."""
import json, math, os, unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
def load(n): return json.load(open(os.path.join(HERE, n), encoding='utf-8'))

R = 6371008.8
def hav(la1, ln1, la2, ln2):
    p = math.pi / 180
    dla = (la2 - la1) * p
    dln = (ln2 - ln1) * p
    m = math.cos((la1 + la2) / 2 * p)
    return math.hypot(dla, dln * m) * R

# ---------- 1. reconstruir aneis dos concelhos ----------
def stitch(ways):
    """Junta troços de fronteira em aneis fechados."""
    segs = [list(w) for w in ways if len(w) >= 2]
    rings, used = [], [False] * len(segs)
    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        ring = segs[i][:]
        changed = True
        while changed and (ring[0] != ring[-1]):
            changed = False
            for j in range(len(segs)):
                if used[j]:
                    continue
                s = segs[j]
                if s[0] == ring[-1]:
                    ring += s[1:];  used[j] = True; changed = True
                elif s[-1] == ring[-1]:
                    ring += s[::-1][1:]; used[j] = True; changed = True
                elif s[-1] == ring[0]:
                    ring = s[:-1] + ring; used[j] = True; changed = True
                elif s[0] == ring[0]:
                    ring = s[::-1][:-1] + ring; used[j] = True; changed = True
        if len(ring) >= 4:
            rings.append(ring)
    return rings

def rdp(pts, eps):
    """Douglas-Peucker, so para desenho."""
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]; bx, by = pts[-1]
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    imax, dmax = 0, -1.0
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        if den == 0:
            d = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / den))
            d = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if d > dmax:
            imax, dmax = i, d
    if dmax <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:imax + 1], eps)[:-1] + rdp(pts[imax:], eps)

def in_ring(lat, lng, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]      # (lat, lng)
        yj, xj = ring[j]
        if (yi > lat) != (yj > lat):
            xint = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lng < xint:
                inside = not inside
        j = i
    return inside

print('a reconstruir concelhos...')
mun = load('mun_pt.json')['elements']
concelhos = []
for rel in mun:
    t = rel.get('tags', {})
    outer, inner = [], []
    for m in rel.get('members', []):
        if m.get('type') != 'way' or not m.get('geometry'):
            continue
        pts = [(round(g['lat'], 6), round(g['lon'], 6)) for g in m['geometry']]
        (inner if m.get('role') == 'inner' else outer).append(pts)
    rings = stitch(outer)
    if not rings:
        continue
    holes = stitch(inner)
    try:
        pop = int(t.get('population', '0'))
    except ValueError:
        pop = 0
    bb = [min(p[0] for r in rings for p in r), min(p[1] for r in rings for p in r),
          max(p[0] for r in rings for p in r), max(p[1] for r in rings for p in r)]
    concelhos.append({'nome': t.get('name', '?'), 'pop': pop,
                      'rings': rings, 'holes': holes, 'bb': bb})
print('  concelhos com geometria:', len(concelhos))

# Ha dois "Calheta" e dois "Lagoa" em Portugal. Sem desambiguar, um apaga o outro
# em qualquer indice por nome.
def nome_unico(c):
    n, lng = c['nome'], c['bb'][1]
    if n == 'Calheta': return 'Calheta (Açores)' if lng < -20 else 'Calheta (Madeira)'
    if n == 'Lagoa':   return 'Lagoa (Açores)'   if lng < -20 else 'Lagoa (Algarve)'
    return n

# ---------- 2. farmacias e unidades de saude ----------
def pts_from(fname, keep):
    out = []
    for e in load(fname)['elements']:
        lat = e.get('lat', (e.get('center') or {}).get('lat'))
        lng = e.get('lon', (e.get('center') or {}).get('lon'))
        if lat is None or lng is None:
            continue
        t = e.get('tags', {})
        if not keep(t):
            continue
        out.append({'lat': lat, 'lng': lng, 'nome': t.get('name') or '', 'tags': t})
    return out

ph = pts_from('ph_pt.json', lambda t: t.get('amenity') == 'pharmacy')

HU_RX = ('centro de saude', 'extensao de saude', 'hospital', 'centro hospitalar',
         'unidade local de saude', 'uls', 'usf', 'ucsp', 'ucc', 'urap', 'unidade de saude')
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower())
                   if unicodedata.category(c) != 'Mn')
def is_legal_hu(t):
    if t.get('amenity') == 'hospital':
        return True
    if t.get('healthcare') in ('hospital', 'centre'):
        return True
    n = norm(t.get('name', ''))
    return any(k in n for k in HU_RX)

hu = pts_from('hu_pt.json', is_legal_hu)

# O OSM tem a mesma farmacia mapeada duas vezes com frequencia (um no e o poligono do
# edificio, ou dois nos com nomes diferentes). Duas farmacias licenciadas distintas a
# menos de 30 m nao existem na pratica, e cada duplicado inflacionaria a saturacao e
# esmagaria a distancia ao vizinho.
def dedup(lst, tol=30.0):
    CELL = 0.002
    g, keep = defaultdict(list), []
    for p in lst:
        gy, gx = int(p['lat'] / CELL), int(p['lng'] / CELL)
        dup = False
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for q in g[(gy + dy, gx + dx)]:
                    if hav(p['lat'], p['lng'], q['lat'], q['lng']) < tol:
                        dup = True
                        break
                if dup: break
            if dup: break
        if not dup:
            keep.append(p)
            g[(gy, gx)].append(p)
    return keep

antes = len(ph)
ph = dedup(ph)
hu = dedup(hu)
print('  farmacias:', len(ph), '(removidos', antes - len(ph), 'duplicados)',
      '| unidades de saude relevantes:', len(hu))

# ---------- 3. vizinho mais proximo (nacional, atravessa fronteiras) ----------
print('a calcular vizinhos...')
CELL = 0.02   # ~2,2 km
grid = defaultdict(list)
for i, p in enumerate(ph):
    grid[(int(p['lat'] / CELL), int(p['lng'] / CELL))].append(i)

for i, p in enumerate(ph):
    gy, gx = int(p['lat'] / CELL), int(p['lng'] / CELL)
    best, bidx = float('inf'), None
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in grid.get((gy + dy, gx + dx), ()):
                if j == i:
                    continue
                d = hav(p['lat'], p['lng'], ph[j]['lat'], ph[j]['lng'])
                if d < best:
                    best, bidx = d, j
    p['dviz'] = best
    p['viz'] = ph[bidx]['nome'] if bidx is not None else ''

# unidade de saude mais proxima de cada farmacia
gridh = defaultdict(list)
for i, h in enumerate(hu):
    gridh[(int(h['lat'] / CELL), int(h['lng'] / CELL))].append(i)
for p in ph:
    gy, gx = int(p['lat'] / CELL), int(p['lng'] / CELL)
    best = float('inf')
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for j in gridh.get((gy + dy, gx + dx), ()):
                d = hav(p['lat'], p['lng'], hu[j]['lat'], hu[j]['lng'])
                best = min(best, d)
    p['dsaude'] = best

# ---------- 4. atribuir farmacias a concelhos ----------
print('a atribuir farmacias a concelhos...')
def locate(lat, lng):
    for c in concelhos:
        bb = c['bb']
        if not (bb[0] <= lat <= bb[2] and bb[1] <= lng <= bb[3]):
            continue
        if any(in_ring(lat, lng, r) for r in c['rings']) and \
           not any(in_ring(lat, lng, h) for h in c['holes']):
            return c
    return None

for c in concelhos:
    c['ph'] = []
for p in ph:
    c = locate(p['lat'], p['lng'])
    p['conc'] = nome_unico(c) if c else None
    if c:
        c['ph'].append(p)
orfas = sum(1 for p in ph if not p['conc'])
print('  farmacias sem concelho:', orfas)

for c in concelhos:
    c['nhu'] = 0
for h in hu:
    c = locate(h['lat'], h['lng'])
    if c:
        c['nhu'] += 1

# ---------- 4b. numero oficial de farmacias (INE 2025) ----------
# O OSM tem lacunas grandes e desiguais. A capitacao tem de sair do numero oficial,
# senao concelhos mal mapeados aparecem como se tivessem imenso espaco livre.
ine_raw = load('ine.json')[0]['Dados']['2025']
ine = {x['geodsg']: int(x['valor']) for x in ine_raw
       if len(x['geocod']) == 7 and x['dim_3'] == '1'}

def ine_key(c):
    """Resolve os nomes que diferem ou se repetem entre INE e OSM."""
    n, lat, lng = c['nome'], c['bb'][0], c['bb'][1]
    if n == 'Castanheira de Pera':  return 'Castanheira de Pêra'
    if n == 'Praia da Vitória':     return 'Vila da Praia da Vitória'
    if n == 'Calheta':              return 'Calheta (R.A.A.)' if lng < -20 else 'Calheta (R.A.M.)'
    if n == 'Lagoa':                return 'Lagoa (R.A.A.)' if lng < -20 else 'Lagoa'
    return n

sem_ine = 0
for c in concelhos:
    v = ine.get(ine_key(c))
    if v is None:
        sem_ine += 1
    c['fine'] = v
print('  concelhos sem numero oficial:', sem_ine,
      '| total oficial:', sum(c['fine'] or 0 for c in concelhos))

# ---------- 5. metricas ----------
def median(v):
    if not v:
        return None
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

saida = []
for c in concelhos:
    lst = c['ph']
    n = len(lst)
    dv = [p['dviz'] for p in lst if p['dviz'] != float('inf')]
    livres = sum(1 for p in lst if p['dviz'] < 1000)
    sub500 = sum(1 for p in lst if p['dviz'] < 500)
    fine = c['fine']
    # Capitacao e "pode abrir" saem sempre do numero oficial do INE.
    cap = round(c['pop'] / fine) if (fine and c['pop']) else None
    eps = 0.0015
    rings = [[[round(y, 5), round(x, 5)] for y, x in rdp(r, eps)] for r in c['rings']]
    rings = [r for r in rings if len(r) >= 4]
    saida.append({
        'n': nome_unico(c), 'pop': c['pop'],
        'f': n,            # farmacias localizadas no OSM (base da analise geometrica)
        'fine': fine,      # numero oficial INE 2025
        'cob': round(100 * n / fine) if fine else None,   # cobertura do OSM, %
        'cap': cap,
        'livres': livres, 'presas': n - livres, 'sub500': sub500,
        'dmed': round(median(dv)) if dv else None,
        'hu': c['nhu'],
        'abrir': bool(fine and c['pop'] and c['pop'] / (fine + 1) >= 3500),
        'g': rings,
        'c': [round((c['bb'][0] + c['bb'][2]) / 2, 5), round((c['bb'][1] + c['bb'][3]) / 2, 5)],
    })

saida.sort(key=lambda x: x['n'])
out = {
    'gerado': '2026-09-08',
    'fonte': 'OpenStreetMap via Overpass; populacao das relacoes administrativas do OSM',
    'totais': {
        'concelhos': len(saida),
        'farmacias_ine': sum(s['fine'] or 0 for s in saida),
        'farmacias': len(ph),
        'unidades_saude': len(hu),
        'livres': sum(s['livres'] for s in saida),
        'presas': sum(s['presas'] for s in saida),
        'sub500': sum(s['sub500'] for s in saida),
    },
    'concelhos': saida,
}
dst = os.path.join(HERE, 'concelhos.json')
json.dump(out, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('escrito', dst, round(os.path.getsize(dst) / 1e6, 2), 'MB')
print('totais:', out['totais'])

# farmacias, ficheiro separado
phout = [{'n': p['nome'], 'y': round(p['lat'], 5), 'x': round(p['lng'], 5),
          'd': None if p['dviz'] == float('inf') else round(p['dviz']),
          's': None if p['dsaude'] == float('inf') else round(p['dsaude']),
          'c': p['conc']} for p in ph]
dst2 = os.path.join(HERE, 'farmacias.json')
json.dump(phout, open(dst2, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('escrito', dst2, round(os.path.getsize(dst2) / 1e6, 2), 'MB')
