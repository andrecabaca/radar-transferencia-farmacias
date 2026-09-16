# Radar de Transferência de Farmácias

Ferramenta de mapa para pré-selecionar locais de transferência de farmácia:
mostra onde a transferência está **legalmente bloqueada** pelas regras de
distância do Infarmed, e o que sobra.

São duas vistas do mesmo problema:

- **`nacional.html`** — os 308 concelhos de uma vez. Serve para escolher onde vale
  a pena procurar.
- **`index.html`** — a análise ao metro de uma zona concreta. Serve para escolher
  a porta.

## Onde está

**https://andrecabaca.github.io/radar-transferencia-farmacias/** — funciona em
qualquer computador ou telemóvel, sem instalar nada.

A origem, os candidatos guardados e as correções manuais ficam no navegador de
quem abre a página, não no servidor. Abrir noutro computador começa do zero.

## Como abrir localmente

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

## Transferências já aprovadas pelo Infarmed

Era o maior ponto cego da ferramenta: um local pode estar livre de farmácias e já
estar entregue a outra por decisão do Infarmed, nos termos do artigo 25.º da
Portaria. O Infarmed publica essas decisões num PDF, *Transferências ao abrigo da
Portaria n.º 352/2012*, atualizado sempre que aprova uma.

O `dados/transferencias.py` lê esse PDF, separa as aprovações das revogações,
fica com o estado mais recente de cada farmácia e situa o destino pela morada.
Das 415 aprovações em vigor, 142 ficaram com posição utilizável.

O mapa distingue duas coisas, e a diferença é importante:

- **Locais tomados** (magenta cheio, com círculo de 500 m): aprovadas nos últimos
  três anos e ainda sem farmácia correspondente no registo. Contam como farmácia
  para o teste das distâncias, porque na prática o sítio está entregue.
- **Histórico** (roxo tracejado, sem círculo): as já executadas e as aprovadas há
  mais de três anos. Não bloqueiam nada. Uma aprovação antiga cujo destino não se
  encontra no registo é quase sempre falha de correspondência de nomes, não um
  local por ocupar há uma década — bloquear por causa dela seria inventar uma
  proibição. Ficam à vista porque dizem para onde a concorrência se mexeu.

Para atualizar: descarregar o PDF por cima de `dados/transferencias-infarmed.pdf`
e correr `python dados/transferencias.py`.

## Concelho limítrofe (artigo 26.º-A)

Um separador só para isto, porque é um teste diferente do resto: não se joga em
metros, joga-se em **capitação** — habitantes por farmácia, contra os 3500
exigidos para abrir farmácia nova.

Escolha o concelho de origem e aparece um quadro com **ela e todos os concelhos
que confinam com ela**, ordenados pela capitação: habitantes por farmácia, quantas
farmácias tem cada um, e uma pastilha verde ou vermelha por linha: **PODE** ou
**A VER** ou **NÃO**. A pastilha conjuga as duas pontas — se o concelho de origem não puder
largar a farmácia, nenhum destino fica verde, por melhor que seja a capitação
dele. O motivo aparece ao passar o rato por cima da linha. A linha da origem mostra a capitação
antes e depois de sair uma farmácia, e diz se o concelho pode sequer exportar. Uma
resposta de conjunto, em vez de sete testes um a um. Clique numa linha para a
escolher como destino.

A lista de destinos mostra **só os concelhos que confinam com a origem** — Beja mostra sete, Alvito mostra quatro — porque
o artigo 26.º-A não admite mais nada. Se já marcou a farmácia a transferir e o
ponto de destino no mapa, os campos preenchem-se sozinhos; e se o ponto testado
cair num concelho que não confina com a origem, o painel di-lo em vez de o deixar
com um campo vazio. Depois responde requisito a requisito:

| Requisito | Onde está |
|---|---|
| Origem com capitação **inferior** à exigível | Lei 26/2011, corpo do artigo |
| Destino com capitação **superior** à exigível | Lei 26/2011, corpo do artigo |
| Depois de sair a farmácia, a origem não passa dos 3500 | Alínea b) |
| Depois de receber, o destino mantém-se acima dos 3500 | Não é do artigo — ver abaixo |
| Há farmácia a menos de 500 m da que se transfere | Alínea a) |
| 500 m entre farmácias no destino | É o que o mapa mostra |

A capitação usa as farmácias licenciadas do registo do Infarmed, não a contagem do
OpenStreetMap, e a população dos concelhos. `dados/concelhos_capitacao.py` gera
`concelhos-capitacao.json`, que inclui a lista de limítrofes de cada concelho.

**O que acontece ao destino depois de receber.** A capitação do destino desce
quando ele ganha uma farmácia, e as setas do quadro mostram isso nas duas pontas.
O artigo 26.º-A **não exige nada ao destino depois da entrada** — as duas condições
cumulativas são expressamente sobre o município de origem. Mas a regra de abrir
farmácia nova exige que a capitação continue acima dos 3500 depois de instalada, e
uma transferência para dentro tem exatamente o mesmo efeito na rede. Por isso o
caso está assinalado a **A VER**, em âmbar, e não a vermelho: cumpre a lei como ela
está escrita, mas é o género de coisa em que o Infarmed repara.

Dos 95 pares que cumprem o artigo, **47 mantêm-se acima dos 3500 depois de receber**.
Os outros 48 passam a estar abaixo — quase sempre porque são concelhos pequenos,
onde acrescentar uma farmácia a duas ou três muda a conta toda.

**Cuidado com a vizinhança.** Os limites vêm simplificados para desenho, por isso
dois concelhos contam como limítrofes quando as fronteiras passam a menos de 400 m
um do outro. Funciona bem em terra; uma fronteira que seja só por água merece
confirmação na certidão.

No país inteiro há 95 pares origem-destino que cumprem a capitação. Não é muito.

## Quem é o dono

Cada farmácia traz o proprietário e o número de farmácias que essa entidade tem
no país, do próprio registo do Infarmed. Passe o rato por cima de uma farmácia
para ver. O resumo da área diz quantos proprietários distintos existem ali e
quantos têm uma só farmácia.

O limite legal de propriedade são quatro farmácias por entidade. Quem já lá está
não pode comprar mais nenhuma — no país inteiro são 22 entidades no limite, contra
2323 proprietários de uma única farmácia.

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
3. **Ler o mapa** — as três camadas ligam-se e desligam-se ali mesmo, por cima do
   resumo: o mapa de cores, os círculos de 500 m e 100 m à volta de cada farmácia,
   e as transferências aprovadas. Vermelho é o que a lei fecha, e a cor diz qual a regra que o
   fecha; âmbar está dentro da margem de erro; o que fica destapado é onde pode
   ir. O resumo diz-lhe que percentagem da área visível está fechada, porquê, e
   de quantos proprietários são as farmácias que a fecham.
4. **Testar um local** — clique num ponto para ver o veredicto requisito a
   requisito.
5. **Candidatos** — guarde os que interessam e descarregue o relatório
   comparativo em Markdown.
6. **Afinar** — margem de segurança, dispensa dos 100 m, camadas do mapa e
   correções manuais. Mexe-se pouco e por isso está no fim.

A ferramenta responde a uma pergunta só: onde é que a lei deixa. Havia antes um
índice de atratividade comercial, que contava lojas e cafés do OpenStreetMap à
volta de cada ponto. Saiu: contar montras não substitui conhecer o negócio, e o
número dava ao palpite um ar de medição que ele não tem. Com ele saiu também o
carregamento de comércio, que era a última coisa que obrigava a esperar.

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
