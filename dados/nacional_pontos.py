# -*- coding: utf-8 -*-
"""Descarrega de uma vez todas as farmacias e unidades de saude de Portugal.

Escreve dados/pontos-osm.json, materia-prima do base_farmacias.py. Sem
isto o radar tinha de consultar o Overpass zona a zona, com 20 a 30 segundos de
espera de cada vez, e o mapa so sabia o que estava dentro da area carregada.

Correr: python dados/nacional_pontos.py
Demora alguns minutos. O Overpass corta consultas nacionais pesadas, por isso a
consulta vai partida por regiao e com repeticoes.
"""
import json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ESPELHOS = ['https://overpass-api.de/api/interpreter',
            'https://overpass.kumi.systems/api/interpreter']
UA = 'RadarTransferenciaFarmacias/1.0 (uso pessoal)'

# Portugal partido em caixas. Uma consulta nacional unica estoira o limite de
# tempo do Overpass; estas passam. Ultimas duas sao Madeira e Acores.
CAIXAS = [
    ('norte',   41.20, -8.90, 42.20, -6.15),
    ('centro-n',40.00, -9.00, 41.20, -6.50),
    ('centro-s',38.90, -9.60, 40.00, -6.80),
    ('lisboa',  38.30, -9.55, 38.90, -8.40),
    ('alentejo',37.80, -9.00, 38.90, -6.90),
    ('algarve', 36.90, -9.00, 37.80, -7.30),
    ('madeira', 32.35, -17.35, 33.15, -16.20),
    ('acores',  36.85, -31.40, 39.80, -24.95),
]

# A area de Portugal filtra Espanha. Sem ela as caixas do interior apanhavam
# farmacias espanholas, que nao pertencem a rede portuguesa e bloqueariam
# falsamente locais junto a raia.
Q = """[out:json][timeout:240];
area["ISO3166-1"="PT"]["admin_level"="2"]->.pt;
(
  nwr["amenity"="pharmacy"](area.pt)({bb});
  nwr["amenity"~"^(hospital|clinic|doctors)$"](area.pt)({bb});
  nwr["healthcare"](area.pt)({bb});
);
out center tags;"""

def consulta(q, tentativas=4):
    ultimo = None
    for t in range(tentativas):
        for url in ESPELHOS:
            try:
                req = urllib.request.Request(
                    url, data=('data=' + urllib.parse.quote(q)).encode(),
                    headers={'User-Agent': UA,
                             'Content-Type': 'application/x-www-form-urlencoded'})
                with urllib.request.urlopen(req, timeout=300) as r:
                    return json.loads(r.read().decode('utf-8'))
            except Exception as e:
                ultimo = e
                print('   falhou (%s): %s' % (url.split('/')[2], e))
        time.sleep(20 * (t + 1))
    raise ultimo

# Mesma classificacao do index.html: so isto pode ser "extensao de saude, centro
# de saude ou estabelecimento hospitalar" para efeitos dos 100 m. Dentistas,
# opticas e fisioterapia contam como comercio, nao como unidade de saude.
HU_RX = re.compile(r'centro de sa[uú]de|extens[aã]o de sa[uú]de|hospital|centro hospitalar|'
                   r'unidade local de sa[uú]de|\bULS\b|\bUSF\b|\bUCSP\b|\bUCC\b|\bURAP\b|'
                   r'unidade de sa[uú]de|urg[êe]ncia', re.I)

def e_legal(t, nome):
    if t.get('amenity') == 'hospital': return True
    if t.get('healthcare') in ('hospital', 'centre'): return True
    return bool(HU_RX.search(nome or ''))

def main():
    ph, hu = {}, {}
    for nome, s, o, n, e in CAIXAS:
        bb = '%s,%s,%s,%s' % (s, o, n, e)
        print('-> %s' % nome)
        j = consulta(Q.format(bb=bb))
        novos_p = novos_h = 0
        for el in j['elements']:
            lat = el.get('lat') or (el.get('center') or {}).get('lat')
            lng = el.get('lon') or (el.get('center') or {}).get('lon')
            if lat is None or lng is None: continue
            t = el.get('tags') or {}
            nm = t.get('name') or t.get('name:pt') or ''
            ident = '%s/%s' % (el['type'], el['id'])
            if t.get('amenity') == 'pharmacy':
                if ident not in ph: novos_p += 1
                ph[ident] = {'i': ident, 'n': nm or 'Farmácia sem nome',
                             'y': round(lat, 5), 'x': round(lng, 5)}
            elif t.get('amenity') in ('hospital', 'clinic', 'doctors') or \
                 t.get('healthcare') in ('hospital', 'centre', 'clinic', 'doctor'):
                if ident not in hu: novos_h += 1
                hu[ident] = {'i': ident,
                             'n': nm or ('Consultório' if t.get('amenity') == 'doctors'
                                         else 'Unidade de saúde'),
                             'y': round(lat, 5), 'x': round(lng, 5),
                             'l': 1 if e_legal(t, nm) else 0}
        print('   +%d farmácias, +%d unidades de saúde' % (novos_p, novos_h))
        time.sleep(5)

    saida = {'gerado': time.strftime('%Y-%m-%d'),
             'farmacias': list(ph.values()),
             'saude': list(hu.values())}
    dest = os.path.join(HERE, 'pontos-osm.json')
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, separators=(',', ':'))
    print('\n%d farmácias, %d unidades de saúde (%d contam para os 100 m)'
          % (len(ph), len(hu), sum(h['l'] for h in hu.values())))
    print('%s — %.1f MB' % (dest, os.path.getsize(dest) / 1e6))

if __name__ == '__main__':
    main()
