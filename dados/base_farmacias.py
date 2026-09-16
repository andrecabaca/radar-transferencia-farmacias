# -*- coding: utf-8 -*-
"""Constroi a base de farmacias a partir do registo oficial do Infarmed.

Porque nao chega o OpenStreetMap: e' colaborativo e esta' incompleto. Em Beja
faltavam-lhe duas das dez farmacias licenciadas, uma delas a Palma. Para o filtro
dos 500 m uma farmacia em falta e' o pior erro possivel, porque pinta de verde um
sitio onde a lei nao deixa transferir.

Quem manda na lista passa a ser o registo do Infarmed (infarmed-registo.json, 2802
farmacias). As coordenadas vem do OSM sempre que a farmacia oficial casa com um ponto
do OSM pelo nome; as restantes sao geocodificadas pela morada e ficam marcadas como
aproximadas, para nao serem lidas como se fossem medicao.

Correr: python dados/base_farmacias.py
Demora perto de uma hora na primeira vez, pelo limite de um pedido por segundo do
Nominatim. As respostas ficam em cache, por isso correr outra vez e' rapido.
"""
import json, math, os, re, time, unicodedata, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = 'RadarTransferenciaFarmacias/1.0 (uso pessoal)'
CACHE = os.path.join(HERE, '.cache-geocode.json')

def caminho(n): return os.path.join(HERE, n)
def ler(n): return json.load(open(caminho(n), encoding='utf-8'))

R = 6371008.8
def dist(la1, ln1, la2, ln2):
    p = math.pi / 180
    return math.hypot((la2 - la1) * p, (ln2 - ln1) * p * math.cos((la1 + la2) / 2 * p)) * R

def sem_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '')
                   if unicodedata.category(c) != 'Mn')

# ---------- nomes ----------
# "OLIVEIRA SUC." no registo e "Farmacia Oliveira" no OSM sao a mesma casa. O que
# distingue uma farmacia da outra e' o nome proprio, nao as palavras de enchimento.
ENCHIMENTO = {'FARMACIA', 'FARMACIAS', 'SUC', 'SUCESSOR', 'SUCESSORES', 'LDA', 'SA',
              'UNIPESSOAL', 'DA', 'DE', 'DO', 'DAS', 'DOS', 'E', 'A', 'O', 'AS', 'OS',
              'EM', 'NO', 'NA', 'PHARMACIA'}

def fichas(nome):
    t = re.sub(r'[^A-Z0-9 ]', ' ', sem_acentos(nome).upper()).split()
    return {x for x in t if x not in ENCHIMENTO and len(x) > 1}

def casam(a, b):
    if not a or not b:
        return False
    comum = a & b
    if not comum:
        return False
    return len(comum) >= min(len(a), len(b))      # um contido no outro

# ---------- moradas ----------
def limpa_rua(rua):
    r = ' '.join((rua or '').split())
    # "RUA X N 2 E RUA Y N 1" fica so' com a primeira
    r = re.split(r'\s+E\s+(?:RUA|AV|AVENIDA|LARGO|PRACA|TRAVESSA)\b', r, 1, flags=re.I)[0]
    r = re.sub(r'\bN\.?\s*[º°o]\.?\s*', '', r)
    r = re.sub(r'\b(Cv|Fracao|Loja|R/C|RC|Piso|Lote)\b.*$', '', r, flags=re.I)
    return r.strip(' ,.-')

# ---------- validacao pelo concelho ----------
# O Nominatim aceita o nome da rua e ignora o resto se lhe convier: "RUA DE MERTOLA"
# de Beja saiu na estrada para Mertola, a 5 km, e "RUA DO PENEDO" saiu a 27 km de
# distancia. Uma coordenada errada e' pior que nenhuma, por isso todo o resultado e'
# confirmado contra o poligono do concelho antes de ser aceite.
_CONC = None
def concelhos():
    global _CONC
    if _CONC is None:
        _CONC = {}
        for c in ler('concelhos.json')['concelhos']:
            _CONC[sem_acentos(c['n']).upper().strip()] = c
    return _CONC

def dentro_anel(y, x, anel):
    dentro = False
    j = len(anel) - 1
    for i in range(len(anel)):
        yi, xi = anel[i][0], anel[i][1]
        yj, xj = anel[j][0], anel[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-15) + xi:
            dentro = not dentro
        j = i
    return dentro

def no_concelho(y, x, nome):
    c = concelhos().get(sem_acentos(nome).upper().strip())
    if not c:
        return True                     # sem poligono, nao ha' como desmentir
    for anel in c['g']:
        if dentro_anel(y, x, anel):
            return True
    # Os poligonos vem simplificados para desenho. Junto ao limite isso chega para
    # excluir por engano um ponto que esta' la' dentro, dai' a folga.
    for anel in c['g']:
        for v in anel:
            if dist(y, x, v[0], v[1]) < 3000:
                return True
    return False

def nominatim(params):
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(
        dict(params, format='json', limit=1, countrycodes='pt'))
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode('utf-8'))

def concelho_de(y, x):
    """Em que concelho cai este ponto. Caixa envolvente primeiro, que e' barato."""
    for nome, c in concelhos().items():
        bb = c.get('_bb')
        if bb is None:
            ys = [v[0] for anel in c['g'] for v in anel]
            xs = [v[1] for anel in c['g'] for v in anel]
            bb = c['_bb'] = (min(ys), max(ys), min(xs), max(xs))
        if not (bb[0] <= y <= bb[1] and bb[2] <= x <= bb[3]):
            continue
        for anel in c['g']:
            if dentro_anel(y, x, anel):
                return nome
    return None

def busca(params, conc, cache):
    """Uma consulta ao Nominatim, validada pelo concelho e guardada em cache."""
    chave = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if chave in cache:
        return cache[chave]
    try:
        j = nominatim(params)
    except Exception as e:
        print('   geocode falhou (%s): %s' % (params.get('street') or params.get('postalcode'), e),
              flush=True)
        return None                            # erro de rede nao vai para cache
    time.sleep(1.1)                            # politica do Nominatim: 1 pedido/s
    r = None
    if j:
        y, x = round(float(j[0]['lat']), 5), round(float(j[0]['lon']), 5)
        if no_concelho(y, x, conc):
            r = {'y': y, 'x': x}
    cache[chave] = r
    return r

def campos(f):
    conc = re.sub(r'\s*\(.*?\)', '', f['conc']).strip()
    return limpa_rua(f['rua']), (f['cp'] or '').strip(), (f['loc'] or '').strip(), conc

def ancora(f, cache):
    """Onde fica, mais ou menos. Serve para ir procurar o ponto do OSM ali ao lado.

    O codigo postal de sete digitos e' o campo mais fiavel do registo: aponta para um
    troco de rua. O nome da rua sozinho engana o Nominatim, que aceita a rua e ignora
    a localidade - "Rua de Mertola" em Beja saiu na estrada para Mertola, a 5 km."""
    rua, cp, loc, conc = campos(f)
    # A pesquisa estruturada do Nominatim e' fraca em Portugal - o campo `county` nao
    # casa com os concelhos e devolve vazio - por isso ha' sempre uma tentativa em
    # texto corrido, que e' o que de facto resolve a maioria das moradas.
    livre = lambda *ps: {'q': ', '.join([x for x in ps if x] + ['Portugal'])}
    for t, prec in ([({'postalcode': cp, 'country': 'Portugal'}, 'cp')] if '-' in cp else []) +                    ([({'street': rua, 'city': loc, 'county': conc, 'country': 'Portugal'}, 'rua')] if rua and loc else []) +                    ([(livre(rua, loc, conc), 'rua')] if rua else []) +                    ([({'street': rua, 'county': conc, 'country': 'Portugal'}, 'rua')] if rua else []) +                    ([(livre(loc, conc), 'localidade')] if loc else []) +                    [(livre(conc), 'concelho')]:
        r = busca(t, f['conc'], cache)
        if r:
            return dict(r, prec=prec)
    return None

def refina(f, anc, cache):
    """So' para as que ficam sem ponto do OSM: tenta a morada ao numero.

    Aceita-se o resultado da rua se estiver perto da ancora. Longe dela e' quase sempre
    uma rua com o mesmo nome noutro sitio, e uma coordenada errada num teste de 500 m
    e' pior do que uma coordenada grosseira mas honesta."""
    rua, cp, loc, conc = campos(f)
    if not rua:
        return anc
    for t in ([{'street': rua, 'city': loc, 'county': conc, 'country': 'Portugal'}] if loc else []) +              [{'q': ', '.join([x for x in (rua, loc, conc) if x] + ['Portugal'])}] +              ([{'street': rua, 'postalcode': cp, 'country': 'Portugal'}] if cp else []):
        r = busca(t, f['conc'], cache)
        if r and dist(r['y'], r['x'], anc['y'], anc['x']) < 3000:
            return dict(r, prec='rua')
    return anc

def main():
    reg = ler('infarmed-registo.json')['farmacias']
    donos = {}
    for f in reg:
        nif = (f.get('nif') or '').strip()
        if nif:
            donos.setdefault(nif, {'nome': f.get('prop') or '', 'n': 0})['n'] += 1
    osm = ler('pontos-osm.json')
    osm_ph, saude = osm['farmacias'], osm['saude']

    # 1. Casar pelo nome dentro do concelho. Isto nao custa pedido nenhum e resolve a
    #    grande maioria; so' o que sobrar vai ao geocodificador, que e' o passo lento.
    print('a atribuir concelho a %d pontos do OSM...' % len(osm_ph), flush=True)
    porconc = {}
    for p in osm_ph:
        p['_t'] = fichas(p['n'])
        c = concelho_de(p['y'], p['x'])
        if c:
            porconc.setdefault(c, []).append(p)
    print('%d concelhos com pontos do OSM' % len(porconc), flush=True)

    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))
        print('cache com %d consultas ja' % len(cache), flush=True)

    saida, exatas, aprox, perdidas = [], 0, 0, []
    usados, porGeocodificar = set(), []
    vistos_id = {}
    for f in reg:
        t = fichas(f['nome'])
        cands = [p for p in porconc.get(sem_acentos(f['conc']).upper().strip(), [])
                 if p['i'] not in usados and casam(t, p['_t'])]
        ident = 'inf/' + f['alvara']
        vistos_id[ident] = vistos_id.get(ident, 0) + 1
        if vistos_id[ident] > 1:                 # o registo tem um alvara repetido
            ident += '-' + str(vistos_id[ident])
        nif = (f.get('nif') or '').strip()
        item = {'i': ident, 'n': f['nome'], 'c': f['conc'],
                'm': ' '.join(f['rua'].split())}
        if nif:
            # d = dono, q = quantas farmacias tem esse dono no pais
            item['d'] = donos[nif]['nome']
            item['q'] = donos[nif]['n']
            item['nif'] = nif
        if len(cands) == 1:
            p = cands[0]
            usados.add(p['i'])
            item.update({'y': p['y'], 'x': p['x'], 'e': 1})
            saida.append(item)
            exatas += 1
        else:
            # zero candidatos, ou varios com o mesmo nome no concelho: so' a morada
            # desempata, e ai' vale a pena gastar o pedido
            porGeocodificar.append((f, item, cands))

    print('%d casadas pelo nome; %d por geocodificar' % (exatas, len(porGeocodificar)),
          flush=True)

    # 2. As que sobraram: situar pela morada e, se houver homonimas no concelho,
    #    escolher a mais proxima.
    try:
        for n, (f, item, cands) in enumerate(porGeocodificar, 1):
            g = ancora(f, cache)
            if not g:
                perdidas.append({'n': f['nome'], 'c': f['conc'],
                                 'm': ' '.join(f['rua'].split())})
                continue
            melhor, dmelhor = None, 1e9
            for p in cands:
                if p['i'] in usados: continue
                d = dist(g['y'], g['x'], p['y'], p['x'])
                if d < 1500 and d < dmelhor:
                    melhor, dmelhor = p, d
            if melhor is None:
                # sem homonima: um unico ponto do OSM coladinho e' a mesma casa
                perto = [p for p in osm_ph if p['i'] not in usados
                         and dist(g['y'], g['x'], p['y'], p['x']) < 120]
                if len(perto) == 1:
                    melhor = perto[0]
            if melhor is not None:
                usados.add(melhor['i'])
                item.update({'y': melhor['y'], 'x': melhor['x'], 'e': 1})
                exatas += 1
            else:
                g = refina(f, g, cache)
                if g['prec'] == 'concelho':
                    perdidas.append({'n': f['nome'], 'c': f['conc'],
                                     'm': ' '.join(f['rua'].split())})
                    continue
                item.update({'y': g['y'], 'x': g['x'], 'e': 0, 'p': g['prec']})
                aprox += 1
            saida.append(item)
            if n % 25 == 0:
                print('   %d/%d geocodificadas' % (n, len(porGeocodificar)), flush=True)
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    finally:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)

    out = {'gerado': time.strftime('%Y-%m-%d'),
           'fonte': 'Registo do Infarmed; coordenadas do OpenStreetMap onde o nome casa',
           'exatas': exatas, 'aproximadas': aprox,
           'proprietarios': len(donos),
           'semPosicao': perdidas,
           'farmacias': saida, 'saude': saude}
    dest = caminho('pontos-nacionais.json')
    json.dump(out, open(dest, 'w', encoding='utf-8'), ensure_ascii=False,
              separators=(',', ':'))
    print()
    print('%d farmacias: %d com coordenada do OSM, %d situadas pela morada'
          % (len(saida), exatas, aprox), flush=True)
    if perdidas:
        print('sem coordenada nenhuma (%d): %s'
              % (len(perdidas), '; '.join(x['n'] + ' / ' + x['c'] for x in perdidas[:25])))
    print('%s - %.1f MB' % (dest, os.path.getsize(dest) / 1e6))

if __name__ == '__main__':
    main()
