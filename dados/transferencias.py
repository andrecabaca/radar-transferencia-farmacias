# -*- coding: utf-8 -*-
"""Le a lista de transferencias aprovadas do Infarmed e situa-as no mapa.

O PDF "Transferencias ao abrigo da Portaria n.o 352/2012" e' a unica fonte publica de
locais que ja' estao tomados por decisao do Infarmed. Sem isto, um local pode parecer
livre no mapa e estar prometido a outra farmacia - que era a maior falha da ferramenta.

O ficheiro esta' em dados/transferencias-infarmed.pdf e e' atualizado pelo Infarmed
sempre que uma transferencia e' aprovada. Para refrescar: descarregar por cima e correr
    python dados/transferencias.py
Escreve dados/transferencias.json.
"""
import json, math, os, re, time, unicodedata, urllib.parse, urllib.request

import pypdf

import base_farmacias as B      # reaproveita a validacao por concelho

import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
PDF = os.path.join(HERE, 'transferencias-infarmed.pdf')
CACHE = os.path.join(HERE, '.cache-geocode-transf.json')
UA = 'RadarTransferenciaFarmacias/1.0 (uso pessoal)'

MESES = {'janeiro': 1, 'fevereiro': 2, 'marco': 3, 'abril': 4, 'maio': 5,
         'junho': 6, 'julho': 7, 'agosto': 8, 'setembro': 9, 'outubro': 10,
         'novembro': 11, 'dezembro': 12}

R = 6371008.8
def dist(la1, ln1, la2, ln2):
    p = math.pi / 180
    return math.hypot((la2 - la1) * p, (ln2 - ln1) * p * math.cos((la1 + la2) / 2 * p)) * R

def sem_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s or '')
                   if unicodedata.category(c) != 'Mn')

def limpo(s):
    return ' '.join((s or '').split())

# ---------- 1. ler o PDF ----------
# O extrator parte palavras ao meio em varias paginas do documento: "con celho",
# "Aven ida", "dist rito". Sem reparar isso perdia-se metade das entradas. A reparacao
# aprende com o proprio documento: uma palavra so' e' colada se a forma junta aparecer
# escrita de seguida noutro sitio do PDF, o que evita inventar palavras.
PALAVRA = re.compile(r'[A-Za-z\u00c0-\u00ff]+')

def vocabulario(t):
    import collections
    c = collections.Counter(w.lower() for w in PALAVRA.findall(t) if len(w) >= 4)
    return {w for w, n in c.items() if n >= 3}

def repara(t, vocab):
    partes = re.split(r'(\s+)', t)
    out, i = [], 0
    while i < len(partes):
        p = partes[i]
        seg = partes[i + 2] if i + 2 < len(partes) else ''
        if (seg and partes[i + 1] == ' '
                and PALAVRA.fullmatch(p or '') and PALAVRA.fullmatch(seg)
                and (len(p) <= 3 or len(seg) <= 3)
                and (p + seg).lower() in vocab
                and not (p.lower() in vocab and seg.lower() in vocab)):
            out.append(p + seg)
            i += 3
            continue
        out.append(p)
        i += 1
    return ''.join(out)

def texto():
    r = pypdf.PdfReader(PDF)
    t = '\n'.join(p.extract_text() or '' for p in r.pages)
    t = re.sub(r'Atualizado em [0-9-]+\s*P.gina \d+ de \d+', ' ', t)
    t = re.sub(r'-\s*\n\s*', '', t)
    return repara(t, vocabulario(t))

RX_HEAD = re.compile(
    r'transfer[\u00ea e]ncia\s+d[ao]\s+(?:Farm[\u00e1a]cia\s+)?(.+?)\s*,?\s*'
    r'sita\s+(?:n[ao]|em)\s+(.+?)\s*,\s*para\s+(?:[ao]\s+)?', re.I | re.S)
RX_PUB = re.compile(r'Publicado\s+em\s*(\d{2}-\d{2}-\d{4})', re.I)
RX_REVOG = re.compile(r'foi\s+revogada\s+a\s+autoriza', re.I)
RX_DELIB = re.compile(r'por\s+(?:delibera[\u00e7c][\u00e3a]o|despacho)\s+de\s+(\d{1,2})\s+de\s+'
                      r'([a-z\u00e7]+)\s+de\s+(\d{4})', re.I)
RX_LOCAL = re.compile(r'concelho\s+d[eo]\s+(.+?)\s*,\s*distrito\s+d[eo]\s+(.{3,32}?)\s*(?:\.|,|$)',
                      re.I | re.S)

def entradas():
    t = texto()
    blocos = re.split(r'(?=Decis[\u00e3a]o\s*-)', t)
    saida, outros = [], 0
    for b in blocos:
        m = RX_HEAD.search(b)
        if not m:
            outros += 1
            continue
        pub = RX_PUB.search(b)
        # O destino vai do fim do cabecalho ate' ao "Publicado em"; depois disso vem o
        # distrito e o concelho da linha seguinte da tabela, que nao sao deste registo.
        cauda = b[m.end(): pub.start() if pub else len(b)]
        loc = RX_LOCAL.search(cauda)
        destino = cauda[:loc.end()] if loc else cauda
        d = RX_DELIB.search(b)
        saida.append({
            'nome': re.sub(r'^Farm[\u00e1a]cia\s+', '', limpo(m.group(1)), flags=re.I),
            'origem': limpo(m.group(2)),
            'destino': limpo(destino).rstrip('.,; '),
            'conc': limpo(loc.group(1)) if loc else '',
            'dist': limpo(loc.group(2)) if loc else '',
            'pub': pub.group(1) if pub else '',
            'delib': ('%04d-%02d-%02d' % (int(d.group(3)),
                                          MESES.get(sem_acentos(d.group(2)).lower(), 0),
                                          int(d.group(1)))) if d else '',
            'revogada': bool(RX_REVOG.search(b)),
        })
    return saida, outros

# ---------- 2. estado atual de cada farmacia ----------
def consolidar(lista):
    """Uma mesma farmacia aparece varias vezes: aprovada, revogada, aprovada de novo.
    So' interessa o ultimo estado de cada par farmacia+destino."""
    def chave(e):
        return (sem_acentos(e['nome']).upper(), sem_acentos(e['conc']).upper())
    def quando(e):
        if not e['pub']:
            return e['delib'].replace('-', '') or '0'
        d, m, a = e['pub'].split('-')
        return a + m + d
    por = {}
    for e in sorted(lista, key=quando):
        por[chave(e)] = e                     # o mais recente fica
    return [e for e in por.values() if not e['revogada']]

# ---------- 3. situar o destino ----------
def morada_destino(e):
    """Corta a parte administrativa: o geocodificador precisa da rua, nao do distrito."""
    d = e['destino']
    d = re.split(r',?\s*(?:Uni[ãa]o das freguesias|freguesia)\s+de\b', d, 1, flags=re.I)[0]
    d = re.split(r',?\s*concelho\s+de\b', d, 1, flags=re.I)[0]
    d = re.sub(r'\bn\.?\s*[º°o]\.?\s*', '', d, flags=re.I)
    d = re.sub(r',?\s*(R/c|R/ch|Loja|Fra[çc][ãa]o|Bloco|Piso|Lote|s/n)\b.*$', '', d, flags=re.I)
    return limpo(d).strip(' ,.-')

def nominatim(params, cache):
    chave = json.dumps(params, sort_keys=True, ensure_ascii=False)
    if chave in cache:
        return cache[chave]
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(
        dict(params, format='json', limit=1, countrycodes='pt'))
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            j = json.loads(r.read().decode('utf-8'))
    except Exception as ex:
        print('   falhou: %s' % ex, flush=True)
        return None
    time.sleep(1.1)
    r = {'y': round(float(j[0]['lat']), 5), 'x': round(float(j[0]['lon']), 5)} if j else None
    cache[chave] = r
    return r

def situar(e, cache):
    """O nome de uma rua repete-se pelo pais fora e o Nominatim aceita o primeiro que
    encontra. Sem confirmar contra o poligono do concelho, punha-se um bloqueio a
    dezenas de quilometros do sitio certo."""
    rua, conc = morada_destino(e), e['conc']
    tentativas = []
    if rua and conc:
        tentativas.append(({'q': ', '.join([rua, conc, 'Portugal'])}, 'rua'))
        tentativas.append(({'street': rua, 'county': conc, 'country': 'Portugal'}, 'rua'))
    if conc:
        tentativas.append(({'q': ', '.join([conc, 'Portugal'])}, 'concelho'))
    for t, prec in tentativas:
        r = nominatim(t, cache)
        if r and B.no_concelho(r['y'], r['x'], conc):
            return dict(r, prec=prec)
    return None

# ---------- 4. juntar tudo ----------
def main():
    lista, outros = entradas()
    print('%d decisoes de transferencia lidas (%d blocos de outro tipo ignorados)'
          % (len(lista), outros), flush=True)
    revog = sum(1 for e in lista if e['revogada'])
    atual = consolidar(lista)
    print('%d revogacoes; %d transferencias aprovadas em vigor' % (revog, len(atual)), flush=True)

    cache = json.load(open(CACHE, encoding='utf-8')) if os.path.exists(CACHE) else {}
    base = json.load(open(os.path.join(HERE, 'pontos-nacionais.json'), encoding='utf-8'))
    farm = base['farmacias']

    saida = []
    try:
        for i, e in enumerate(atual, 1):
            g = situar(e, cache)
            if not g or g['prec'] == 'concelho':
                continue
            # A farmacia ja' mudou de facto, ou o destino ainda esta' por ocupar? Se o
            # registo ja' tem esta farmacia junto ao destino, a mudanca esta' feita e o
            # ponto ja' esta' no mapa. Se nao tem, aquele sitio esta' prometido a alguem.
            # Ja' se mudou? Se o registo do Infarmed tem esta farmacia junto ao destino,
            # a mudanca esta' feita e o ponto ja' esta' no mapa pelo registo. Os nomes
            # nao batem letra a letra ("do Furadouro" no PDF, "FURADOURO" no registo),
            # por isso compara-se por palavras; e as duas posicoes sao aproximadas, o que
            # obriga a uma folga generosa.
            alvo = B.fichas(e['nome'])
            perto = None
            for p in farm:
                if not B.casam(alvo, B.fichas(p['n'])):
                    continue
                d = dist(g['y'], g['x'], p['y'], p['x'])
                if perto is None or d < perto:
                    perto = d
            feita = perto is not None and perto < 800
            # Uma aprovacao antiga cujo destino nao se encontra no registo e' quase
            # sempre falha de correspondencia, nao um local por ocupar ha' dez anos.
            # Bloquear por causa dela seria inventar uma proibicao. So' as recentes
            # tapam o local; as outras ficam no mapa como informacao.
            ano = int(e['pub'][-4:]) if e['pub'] else 0
            bloqueia = (not feita) and ano >= int(time.strftime('%Y')) - 3
            saida.append({'n': e['nome'], 'y': g['y'], 'x': g['x'], 'c': e['conc'],
                          'm': e['destino'], 'o': e['origem'], 'pub': e['pub'],
                          'del': e['delib'], 'p': g['prec'],
                          'f': 1 if feita else 0, 'b': 1 if bloqueia else 0})
            if i % 25 == 0:
                print('   %d/%d situadas' % (i, len(atual)), flush=True)
                json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)
    finally:
        json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False)

    feitas = sum(x['f'] for x in saida)
    bloqueiam = sum(x['b'] for x in saida)
    out = {'gerado': time.strftime('%Y-%m-%d'),
           'fonte': 'Infarmed, Transferencias ao abrigo da Portaria n.o 352/2012',
           'transferencias': saida}
    dest = os.path.join(HERE, 'transferencias.json')
    json.dump(out, open(dest, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print()
    print('%d transferencias no mapa: %d ja executadas, %d por ocupar, das quais %d '
          'recentes que tapam o local' % (len(saida), feitas, len(saida) - feitas, bloqueiam))
    print('%s - %.2f MB' % (dest, os.path.getsize(dest) / 1e6))

if __name__ == '__main__':
    main()
