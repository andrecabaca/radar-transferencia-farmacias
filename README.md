# Radar de Transferência de Farmácias

Ferramenta de mapa para pré-selecionar locais de transferência de farmácia:
mostra onde a transferência está **legalmente bloqueada** pelas regras de
distância do Infarmed e, dentro do que sobra, onde o local é **comercialmente
mais interessante**.

São duas vistas do mesmo problema:

- **`nacional.html`** — os 308 concelhos de uma vez. Serve para escolher onde vale
  a pena procurar.
- **`index.html`** — a análise ao metro de uma zona concreta. Serve para escolher
  a porta.

## Como abrir

Duplo clique em `Abrir Radar.bat`. Abre o navegador em `http://localhost:8777`.
Feche a janela preta quando terminar.

Precisa de Python instalado (já está) e de ligação à internet — os dados vêm do
OpenStreetMap em tempo real.

## O mapa nacional

Abre em `http://localhost:8777/nacional.html` ou pela ligação no topo do radar.
Colore os concelhos por uma de cinco métricas, tem ranking clicável, pesquisa por
nome e exporta a tabela completa em CSV. Clicar num concelho mostra o detalhe e o
botão que salta para a análise ao metro já enquadrada nesse concelho.

As métricas:

| Métrica | O que responde |
|---|---|
| Farmácias que podem mudar-se | Quantas têm outra a menos de 1000 m e por isso não estão presas ao raio de 750 m |
| Capitação | Habitantes por farmácia, com o número oficial do INE |
| Pode abrir farmácia nova | Se a capitação se mantém acima de 3500 depois de instalada mais uma |
| Saturação da rede | Percentagem de farmácias já a menos de 500 m de outra |
| Distância entre vizinhas | Mediana da distância de cada farmácia à mais próxima |

### De onde vêm os dados nacionais

`dados/processa.py` constrói `dados/concelhos.json` e `dados/farmacias.json` a
partir de três fontes:

- **Limites e população dos concelhos**: relações administrativas do OpenStreetMap
  (nível 7), com os polígonos simplificados para desenho mas com a geometria
  completa usada para atribuir cada farmácia ao seu concelho.
- **Número oficial de farmácias**: INE, Estatísticas das Farmácias 2025. É este o
  número usado na capitação — o OpenStreetMap sozinho daria capitações falsas em
  concelhos mal mapeados.
- **Localização das farmácias e unidades de saúde**: OpenStreetMap.

O OpenStreetMap tem 2706 das 2921 farmácias licenciadas, ou seja 93%, mas a
cobertura é muito desigual: em Lisboa está praticamente completa, no Grande Porto
falta cerca de metade. Por isso cada concelho traz a sua percentagem de cobertura,
e abaixo de 70% a aplicação avisa que as contas de distâncias não são de fiar ali.

Farmácias a menos de 30 m umas das outras são tratadas como o mesmo
estabelecimento: o OpenStreetMap mapeia com frequência a mesma farmácia duas
vezes, uma como ponto e outra como edifício. Sem isso a saturação vinha inflacionada.

Para atualizar os dados, correr `python dados/processa.py` depois de voltar a
descarregar os ficheiros do Overpass e do INE indicados no cabeçalho do script.

## De onde vêm as farmácias

A lista é a do **registo do Infarmed**, não a do OpenStreetMap. As farmácias
licenciadas do país inteiro estão em `dados/pontos-nacionais.json`, carregado
assim que a página abre: a camada de bloqueio está certa em qualquer ponto do
país sem esperar por nada.

Foi o OpenStreetMap que obrigou a esta mudança. Em Beja faltavam-lhe duas das dez
farmácias licenciadas, incluindo a Palma. No teste dos 500 m, uma farmácia em
falta é o pior erro possível: pinta de verde um sítio onde a lei não deixa
transferir.

**Posições exatas e posições aproximadas.** O registo do Infarmed tem a lista
certa mas não tem coordenadas, só moradas. Onde a farmácia oficial casa com um
ponto do OpenStreetMap pelo nome, fica com a coordenada do OSM, que é precisa. As
restantes são geocodificadas pela morada: aparecem no mapa **a tracejado**, com a
morada no tooltip, e o veredicto avisa que ali a distância tem de ser confirmada
em planta. Uma posição aproximada pode estar dezenas de metros ao lado.

O botão passou a servir só para o **comércio e serviços**, que alimentam o índice
de atratividade. Esses são milhões de pontos, não cabem num ficheiro do país, e só
fazem falta quando já escolheu a zona.

Abaixo do nível de zoom 12 o radar não avalia: 500 m valem aí menos de sete pixels,
e um mapa quase todo verde seria mentira. Para a vista de longe existe o mapa
nacional.

### Atualizar os dados

Três passos, por esta ordem:

1. `python dados/nacional_pontos.py` — farmácias e unidades de saúde do
   OpenStreetMap para `pontos-osm.json`. Filtra pela área de Portugal, para que
   farmácias espanholas junto à raia não bloqueiem falsamente locais portugueses.
2. Raspar o registo do Infarmed para `dados/infarmed-registo.json`, a partir da
   [Listagem de Farmácias](https://extranet.infarmed.pt/LicenciamentoMais-fo/pages/public/listaFarmacias.xhtml).
   É a única parte que não está automatizada: o portal é JSF e não tem API.
3. `python dados/base_farmacias.py` — cruza os dois e escreve
   `pontos-nacionais.json`. Demora perto de uma hora da primeira vez, por causa do
   limite de um pedido por segundo do Nominatim. Fica tudo em cache.

## Fluxo de trabalho

O painel da esquerda segue a ordem por que o trabalho se faz. O botão no canto
superior direito esconde-o e dá o ecrã todo ao mapa.

1. **Localizar a zona** — escreva o concelho ou a morada e carregue em Procurar.
   Aproxime até ver a zona de interesse. Procurar por um concelho inteiro
   ("Beja") devolve um limite de milhares de km²: nesses casos o mapa centra-se
   na localidade e avisa-o. As farmácias já lá estão, do país inteiro, com
   **1100 m de folga para lá da borda** do ecrã, para que uma farmácia logo a
   seguir ao limite não passe despercebida.
2. **Farmácia a transferir** — marque a localização atual. Sem isto não é
   possível testar o requisito do artigo 26.º n.º 2 a) nem o raio de 750 m.
3. **Ler o mapa** — vermelho é o que a lei fecha, e a cor diz qual a regra que o
   fecha; âmbar está dentro da margem de erro; o que fica destapado é onde pode
   ir. O resumo diz-lhe que percentagem da área visível está fechada e porquê.
   No modo *Onde compensa*, o verde acende consoante o movimento à volta.
4. **Testar um local** — clique num ponto para ver o veredicto requisito a
   requisito, com o índice de atratividade repartido.
5. **Candidatos** — guarde os que interessam e descarregue o relatório
   comparativo em Markdown.
6. **Afinar** — margem de segurança, dispensa dos 100 m, camadas do mapa,
   carregamento do comércio e correções manuais. Mexe-se pouco e por isso está
   no fim.

O estado fica guardado no navegador. Fechar e reabrir mantém origem, candidatos,
parâmetros e pontos acrescentados à mão.

## Regras codificadas

Base legal: Decreto-Lei n.º 307/2007 de 31 de agosto, artigos 26.º e 26.º-A
(redação do Decreto-Lei n.º 58/2024), e Portaria n.º 352/2012 de 30 de outubro,
artigo 2.º (redação da Portaria n.º 375/2025/1 de 4 de novembro, em vigor desde
5 de novembro de 2025).

| Requisito | Valor | Aplica-se à transferência? |
|---|---|---|
| Distância entre farmácias | 500 m | Sim |
| Distância a centro de saúde, extensão de saúde ou hospital | 100 m | Sim, salvo freguesias com menos de 4000 habitantes |
| Farmácia a menos de 1000 m da localização atual | 1000 m | Sim, com as dispensas do n.º 4 |
| Raio máximo do destino quando o requisito acima falha | 750 m | Sim |
| Parecer favorável da câmara municipal | — | Sim, obrigatório e vinculativo |
| Capitação de 3500 habitantes por farmácia | — | **Não.** Só à abertura de novas farmácias |
| Carência desde a abertura | 5 anos | Sim |

**Atenção:** os 350 m que constavam da Portaria n.º 1430/2007 já não estão em
vigor. Desde novembro de 2025 são 500 m.

## Como as distâncias são medidas

A lei manda medir **em linha reta, entre os dois pontos mais próximos dos
limites exteriores dos edifícios** — não entre as entradas nem entre os centros.
Os pontos do OpenStreetMap são entradas ou centroides, por isso a distância que a
app calcula é **maior** que a distância legal, o que empurraria os veredictos
para um otimismo perigoso.

É para isso que serve a **margem de segurança** (30 m por defeito): um local só
aparece verde se estiver a 500 m + margem. A faixa âmbar é a zona onde o
resultado depende da geometria concreta dos edifícios e tem de ser medida em
planta.

## Índice de atratividade (0-100)

Não tem valor legal. É uma heurística para ordenar os locais que já passaram no
filtro legal.

- **Comércio e serviços em 250 m — 50 pontos.** Pontos do OSM ponderados por
  capacidade de gerar tráfego a pé (supermercado 3, banco e correios 2, café 1,
  escritório 0,5) e com peso decrescente com a distância.
- **Proximidade a unidades de saúde — 30 pontos.** Máximo entre os 100 m e os
  350 m, a decair até zero aos 1200 m. Abaixo dos 100 m o local está bloqueado.
- **Folga face à concorrência — 20 pontos.** Cresce dos 500 m aos 1500 m da
  farmácia mais próxima. Um local a 510 m é legal mas fica colado à concorrência.

## O que isto não faz

- **Não substitui a certidão camarária** do artigo 20.º n.º 1 d) da Portaria,
  que é a prova legal das distâncias, nem a decisão de aptidão do Infarmed.
- **Não conhece os pedidos de transferência de terceiros em curso**, que
  bloqueiam locais nos termos do artigo 25.º da Portaria. Só o Infarmed publica
  essa informação.
- **Não conta a população da freguesia.** A dispensa dos 100 m para freguesias
  com menos de 4000 habitantes é um interruptor manual — confirme nos Censos.
- **Não verifica as condições de funcionamento** (áreas e divisões mínimas).
- **Não trata a capitação** para transferências entre concelhos limítrofes
  (artigo 26.º-A), que exige dados do INE por município.

Os dados do OpenStreetMap estão incompletos, sobretudo fora dos centros urbanos.
Trate o resultado como uma pré-seleção: serve para descartar depressa o que é
impossível e para ordenar o que vale a pena ir ver ao terreno.
