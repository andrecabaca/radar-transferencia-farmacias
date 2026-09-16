# -*- coding: utf-8 -*-
"""Capitacao e vizinhanca de cada concelho, para o teste do artigo 26.o-A.

A transferencia para concelho limitrofe joga-se toda em dois numeros: a capitacao
do concelho de origem e a do destino. Capitacao e' habitantes por farmacia, e a
referencia legal sao os 3500 habitantes por farmacia exigidos para abrir farmacia
nova (art. 2.o n.o 1 a) da Portaria 352/2012).

Escreve dados/concelhos-capitacao.json com, para cada um dos 308 concelhos:
populacao, farmacias licenciadas, capitacao, e a lista de concelhos limitrofes.

Correr: python dados/concelhos_capitacao.py
Nao consulta a internet: usa o registo do Infarmed e os limites ja' descarregados.
"""
import json, math, os, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CAPITACAO_EXIGIVEL = 3500

def ler(n):
    return json.load(open(os.path.join(HERE, n), encoding='utf-8'))

def chave(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s or '')
                if unicodedata.category(c) != 'Mn')
    return s.upper().strip()

R = 6371008.8
def dist(la1, ln1, la2, ln2):
    p = math.pi / 180
    return math.hypot((la2 - la1) * p, (ln2 - ln1) * p * math.cos((la1 + la2) / 2 * p)) * R

# ---------- vizinhanca ----------
# Os poligonos vem simplificados para desenho, por isso dois concelhos vizinhos ja' nao
# partilham vertices exatos. Consideram-se limitrofes quando as fronteiras passam a
# menos de FOLGA um do outro. Com folga a mais, Lisboa ficava limitrofe de Almada por
# cima do Tejo; com folga a menos, perdiam-se vizinhancas reais na serra.
FOLGA = 400

def caixa(c):
    ys = [v[0] for anel in c['g'] for v in anel]
    xs = [v[1] for anel in c['g'] for v in anel]
    return min(ys), max(ys), min(xs), max(xs)

def vertices(c, passo=1):
    return [v for anel in c['g'] for v in anel[::passo]]

def limitrofes(concelhos):
    cx = {c['n']: caixa(c) for c in concelhos}
    vt = {c['n']: vertices(c) for c in concelhos}
    dLat = FOLGA / 111320.0
    viz = {c['n']: set() for c in concelhos}
    nomes = [c['n'] for c in concelhos]
    for i, a in enumerate(nomes):
        ay0, ay1, ax0, ax1 = cx[a]
        dLngA = FOLGA / (111320.0 * math.cos(((ay0 + ay1) / 2) * math.pi / 180))
        for b in nomes[i + 1:]:
            by0, by1, bx0, bx1 = cx[b]
            if ay0 - dLat > by1 or by0 - dLat > ay1: continue
            if ax0 - dLngA > bx1 or bx0 - dLngA > ax1: continue
            achou = False
            for p in vt[a]:
                if achou: break
                for q in vt[b]:
                    if abs(p[0] - q[0]) > dLat or abs(p[1] - q[1]) > dLngA:
                        continue
                    if dist(p[0], p[1], q[0], q[1]) <= FOLGA:
                        achou = True
                        break
            if achou:
                viz[a].add(b)
                viz[b].add(a)
    return viz

def main():
    concelhos = ler('concelhos.json')['concelhos']
    reg = ler('infarmed-registo.json')['farmacias']

    # Quantas farmacias licenciadas tem cada concelho. E' o registo do Infarmed que
    # manda, nao a contagem do OpenStreetMap: a capitacao calculada sobre o OSM dava
    # numeros falsos nos concelhos mal mapeados.
    conta = {}
    for f in reg:
        conta[chave(f['conc'])] = conta.get(chave(f['conc']), 0) + 1

    print('a calcular vizinhancas dos %d concelhos...' % len(concelhos), flush=True)
    t0 = time.time()
    viz = limitrofes(concelhos)
    print('feito em %.0f s' % (time.time() - t0), flush=True)

    saida = []
    for c in concelhos:
        n = conta.get(chave(c['n']), 0)
        pop = c.get('pop') or 0
        cap = round(pop / n) if n else None
        # Se sair uma farmacia, a capitacao sobe. A alinea b) do artigo exige que nao
        # passe do exigivel.
        cap_saida = round(pop / (n - 1)) if n > 1 else None
        # E ao receber uma, desce. O artigo 26.o-A nao exige nada ao destino depois da
        # entrada, mas a regra de abrir farmacia nova exige, e o efeito na rede e' o
        # mesmo. Fica o numero, para se ver.
        cap_entrada = round(pop / (n + 1)) if pop else None
        saida.append({
            'n': c['n'], 'pop': pop, 'f': n, 'cap': cap, 'capSaida': cap_saida,
            'capEntrada': cap_entrada,
            'lim': sorted(viz[c['n']]),
        })

    out = {'gerado': time.strftime('%Y-%m-%d'),
           'capitacaoExigivel': CAPITACAO_EXIGIVEL,
           'fonte': 'Farmacias do registo do Infarmed; populacao e limites dos concelhos',
           'concelhos': saida}
    dest = os.path.join(HERE, 'concelhos-capitacao.json')
    json.dump(out, open(dest, 'w', encoding='utf-8'), ensure_ascii=False,
              separators=(',', ':'))

    semviz = [c['n'] for c in saida if not c['lim']]
    print('%d concelhos; %d sem vizinhos (ilhas)' % (len(saida), len(semviz)))
    print('media de vizinhos: %.1f' % (sum(len(c['lim']) for c in saida) / len(saida)))
    print('%s - %.2f MB' % (dest, os.path.getsize(dest) / 1e6))

if __name__ == '__main__':
    main()
