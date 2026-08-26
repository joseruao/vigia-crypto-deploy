# Vigia Crypto — Notas de Investigação

> Colar este ficheiro no Claude normal para planear estratégia.
> Atualizar no Claude Code após cada sessão de execução.

---

## ⚖️ DEVIL'S ADVOCATE — Parte LABORAL "super completa" (20 Ago 2026)

Backend canónico: `devil-azure/` (App Service `vigia-devil-mistral.azurewebsites.net`,
Mistral, região UE). Frontend `/devil` → `/devils-advocate` (Vercel via remote `deploy`).

### ✅ Feito (commit `36fe217`, deploy Azure feito)
- **Campos estruturados laborais OPCIONAIS** no schema: `observacoes`, `cronologia`,
  `testemunhas`, `fundamentos_de_despedimento`, `calculo_de_indemnizacao`,
  `procedimento_disciplinar` — default vazio, contrato não quebra.
- **FASE 13 — CHECKLIST LABORAL** no modo pre_filing (impugnação de despedimento,
  contestação, peças/incidentes, cronologia, testemunhas, cálculo de indemnização,
  juros/custas, anti-alucinação). Só injetada para Laboral.
- `_normalize_model_payload` tolera dicts em campos string (ex.: `procedure` como
  objeto → JSON string) e normaliza os campos laborais. `_PROMPT_VERSION` na cache
  key (invalida cache de 1h).
- UI: TimelineBlock (cronologia), WitnessGrid (testemunhas), FundamentosBlock,
  IndemnizacaoGrid + secções content-driven (só aparecem com conteúdo); meta no
  Sumário com tipo de documento + objetivo.
- Testes: `devil-azure/tests/test_devils_advocate.py` (20 testes, pytest no venv).
  Smoke real local mistral: pre_filing (299s) e adversarial (109s) laboral com campos
  preenchidos + Fiscal sem regressão (111s).

### ⚠️ Quirks confirmados
- Console Windows cp1252 → acentos aparecem como `�` na saída do pytest/curl (só display).
- `az webapp deploy` demora >5 min (build Oryx + pip) — correr em background.
- FASE 13 só ativa com `legal_area` contendo "labor"/"trabalh".
- Testes: `cd devil-azure && .venv/Scripts/python.exe -m pytest tests -q` (pytest dev-only).

---

## ⚖️ DEVIL'S ADVOCATE — Audit pré-advogado (27 Jun 2026)

Ferramenta jurídica (backend `Api/services|routes/devils_advocate.py`, frontend
`/devil`). Lançada e a funcionar em produção (Railway + Vercel). Modelo via env
`DEVILS_ADVOCATE_MODEL` (default `gpt-4o-mini`; testado e bom em `gpt-5.5`).

### ✅ Feito neste audit
- **Timeout + retries no OpenAI** (90s, 2 retries) e **erros mapeados para mensagens
  PT amigáveis** (503) em vez de "analysis failed"/spinner infinito. Falha de parse do
  JSON da IA → mesma via.
- **Timeout no fetch do frontend** (2 min, AbortController) → "A análise demorou demasiado".
- **Rate-limit default 20 → 40/hora por IP** (mais folga para o advogado iterar; ainda protege).
- (Antes neste dia) auth fail-closed por código de acesso, rate-limit, aviso RGPD,
  guarda anti prompt-injection, truncagem visível, dedup das referências legais,
  botão Exportar PDF, prompt afinado p/ profundidade, código gpt-5-safe (sem temperature).

### NEEDS_DECISION — para o José decidir (não bloqueiam testes com advogado)
1. **Modelo vs custo:** `gpt-5.5` ~18 cênt/doc (qualidade topo) vs `gpt-5.4` ~9 cênt
   (metade do preço, qualidade quase igual). Recomendo testar o mesmo doc nos dois e
   ficar no 5.4 se for equivalente. É só mudar `DEVILS_ADVOCATE_MODEL` no Railway.
2. **Arquitetura de privacidade p/ produção real:** atual = OpenAI/EUA + aviso honesto
   (ok p/ beta). Para escalar com dados reais de clientes: ou **UE+DPA** (Mistral / Azure
   OpenAI região UE — mantém qualidade, defensável RGPD/segredo) ou **Llama local/self-hosted**
   (tira o aviso por completo, mas qualidade cai e exige hardware). Decidir antes de uso real.
3. **Railway sem créditos:** dashboard marcou "8 days or $3.81 left" (27 Jun). Quando esgotar,
   backend cai (502). Adicionar crédito antes disso.

### Limitações conhecidas (menores, não corrigidas — aceitáveis p/ beta)
- Rate-limit é em memória por processo (não partilhado entre workers/instâncias).
- Em modo EN, os títulos das secções do relatório ficam em PT (conteúdo vem em EN). Público é PT.
- Sem cap de `max_tokens` na chamada (evita truncar o JSON; o timeout de 90s é o limite).

---

## ⚽ FOOTBALL LAB — Auditoria do Codex aplicada (24 Jun 2026, commit 74d211b)

Codex fez auditoria de dados. Conclusão dele: **não há fonte grátis decente de xG/eventos
táticos** ao nível pago; o problema real do produto não era visual, era **confiança nos dados**.

### ✅ FEITO (recomendação #1 do Codex — esforço baixo, valor altíssimo)
- **Data Confidence** em todos os relatórios: provider, nº de jogos, remates c/ coordenadas,
  xg_source, lineup_source, confiança (low/medium/high) + avisos. Web (`DataConfidenceBar`) +
  PDF (`_data_confidence_box`, página 1). `fi.build_data_quality()`.
- **Dedupe de golos** por jogo (scorer+minuto+equipa) — corrige marcador a aparecer 2x (ex.
  Vinícius 45+3'); propaga a shot maps e danger scores.
- **Anti-alucinação:** `_confidence_instruction()` injecta o bloco de confiança nos dois prompts;
  confiança baixa = LLM proibido de afirmar traços como facto ("defensive solidity" com 3 jogos).
- **Relabel "Probable XI" → "Probable XI (inferred from last lineup)"** (vem do último onze ESPN
  + heurística posicional, não é info oficial).

### NEEDS_DECISION — modelo próprio de xG (recomendação #2 do Codex, esforço médio/alto)
Codex recomenda treinar um xG caseiro com **StatsBomb Open Data** (grátis, GitHub: tem `location`,
`shot.body_part`, `shot.type`, `shot.statsbomb_xg`) e aplicá-lo às coordenadas de remate do ESPN.
Features: distância, ângulo, x/y, parte do corpo, zona, situação (penalty fixo ~0.76). Expectativa
honesta: xG básico útil p/ ordenar chances, não igual ao comercial (sem GK/defensores/pressão).
**NÃO comecei sozinho** — é tarefa de várias horas (download dados, feature eng., treino, validação)
e meia-feita minaria a camada de confiança recém-criada. Decidir em sessão dedicada COM o José.
Quando feito: `xg_source` passa de "none" → "internal_estimate" e o aviso "sem xG" desaparece.

### Outras pistas do Codex (roadmap)
- **Football-Data.co.uk** (CSVs grátis: resultados + odds históricas + cantos/cartões/faltas) → bom
  p/ **backtesting** do Football Bet. NÃO resolve odds históricas de mercados de cantos (essas, grátis,
  são fracas).
- **Wyscout open dataset (Figshare)** — eventos espaço-temporais top-5 ligas 2017/18 + Mundial 2018 +
  Euro 2016 (~1941 jogos, 3.25M eventos JSON) → treinar modelos de eventos/tática (histórico, não actual).
- Understat (xG das 5 grandes, scraping/HTML, risco alto) e FBref (403, evitar).

---

## ⚽ FOOTBALL BET — Pending Decisions (24 Jun 2026)

> Projecto novo: value betting reaproveitando o motor do Football Lab. Ver memória
> project_football_bet.

### ✅ RESOLVIDO — key recebida, probes corridos (key no .env: ODDS_API_KEY)
Resultado empírico real (tier grátis, 500 créditos/mês; gastámos ~11):
- **Golos O/U, BTTS, h2h:** cobertura larga (golos = 7+ casas), mesmo semanas antes. Mercado mais explorável.
- **Cantos & cartões O/U:** EXISTEM mas quase só de **Pinnacle** (casa afiada), e só no endpoint
  **por-evento** e **perto do kickoff**. → ferramenta corre em **dia de jogo**, não dias antes.
- 5 grandes ligas fora de época até **~21 Ago 2026**; em Junho só o Mundial está a decorrer.

### Estado do motor (feito + validado)
- `bet_odds.py` / `bet_model.py` / `bet_engine.py` + `BET_README.md`. Modelo Poisson **validado**
  (`_test_bet_model.py`); pipeline ponta-a-ponta **provado ao vivo** no Mundial (`_run_bet_scan.py`).
- Histórico do modelo vem do ESPN (cantos/cartões por jogo, football_analysis.py). 5 ligas EU
  adicionadas ao `_COMPS` (slugs ESPN) para Agosto.

### NEEDS_DECISION (não-bloqueante) — quando as ligas abrirem (Ago)
Correr scan em dia de jogo na Série A/EPL, calibrar `LEAGUE_PRIOR` com médias reais, e decidir se
vale a pena endpoint+frontend (reusar stack do Lab). Não construir frontend agora: mostraria só
ruído do Mundial (amostras de 2 jogos → tudo "thin sample").

---

## 🔴 GENIUS — RECONSTRUÇÃO FINANCEIRA ON-CHAIN (23 Jun 2026) — LER ANTES DE SUBMETER CFTC

A submissão CFTC actual (`GENIUS_CFTC_Submission_June2026.docx`) tinha números **errados por ordens
de magnitude**. Reconstrução completa via Dune (BSC) + Etherscan V2 (ETH) + Arkham labels:

**Contrato GENIUS (BSC):** `0x1f12b85aac097e43aa1555b2881e98a51090e9a6`

**FACTOS VERIFICADOS (cada número tem hash on-chain):**
- gianmarco (`0xD8BDd8`) recebeu **2,377,157 GENIUS** do Ghost Order hub (`0x199A74`) em **16 Abr 2026**.
- Hub obteve os tokens 13-14 Abr: **1,978,642 (83%) de `0x3d90f66b`** (= TransparentUpgradeableProxy,
  contrato LP/router — NÃO "OTC Seller A de 252k", erro do 1.txt) + ~398k de 8 wallets OTC (1 tx cada).
- GENIUS era **ultra-líquido desde o TGE** (dezenas de M$/dia em DEX PancakeSwap/Uniswap).
- gianmarco: round-trip via relay `0x0ef2fb1a` (25-29 Mai) → estacionou em **holding `0x9d9695`** (9 Jun, 2,376,147).
- **22 Jun 2026 (alerta disparou!): holding VENDEU 712,807 GENIUS → 280,811 USDT** (timestamps idênticos
  11:34–16:25 UTC, via DEX `0x6f0538`/`0x8f10b468`). Ainda detém **~1,663,340 GENIUS** (~$655k).

**O QUE ESTAVA ERRADO NO DOCX:**
- ❌ "$1.64M Coinbase + $7.38M KuCoin = $9M saídas" → FALSO para GENIUS. Em ETH: gianmarco→KuCoin dist
  = só **$22,904** (não $7.38M); holding `0x9d9695` em ETH = **0 transacções** (vazio).
- ❌ Coinbase real: gianmarco→Coinbase Deposit (`0xae84160ab`) = só **$45,548** (não $1.64M). Nexo US existe
  mas é pequeno. `0xef4fb24a` (maior dest ETH, $235k) = **deBridge Finance** (bridging), não saída.
- ❌ Custo "$52k" e "$812k" ambos errados. Hub é router partilhado ($174M) — custo real **ofuscado pelo
  próprio Ghost Order** (isto É evidência de ocultação, usar como tal).
- ❌ "Posição liquidada $2.69M / 45.9x realizado" → FALSO. Lucro era **não-realizado**; só agora (22 Jun)
  começaram a vender. Realizado até hoje = **$280,811**.

**⚠️ CORRECÇÃO 24 Jun — o "45x / $1.01 listing" TAMBÉM estava errado.** Preço real do GENIUS
(contrato 0x1f12b85a, VWAP dex.trades): 16 Abr (aquisição) = **$0.63**; 22 Mai (listing) = $0.57;
22 Jun (venda) = $0.40. O token DESCEU, não subiu. O "$1.01 / TGE $0.022 / 45x" do dossier era
mais um erro. Consequência: os $280k "realizados" NÃO são lucro provado — ele recebeu a $0.63 de
mercado e vende a $0.40. A entrada real (custo) está ofuscada pelo hub. **GENIUS não é um "smart
money win" defensável.** Query: 7804416. Lição: verificar SEMPRE preço por contrato antes de
chamar "lucro" a uma venda.

**MODELO HONESTO PARA A SUBMISSÃO:**
- Adquiridos 2,377,157 GENIUS pré-listing (Abr) via ferramenta de ocultação Ghost Order.
- MNPI: 39 dias antes do anúncio Binance (22 Mai). Pico não-realizado ~$2.4M (@ $1.01).
- Realizado: $280,811 (22 Jun, 1ª venda). Ainda detém ~1.66M GENIUS (~$655k). Liquidação EM CURSO.
- Identidades (gianmarco_eth/TaiwanNumbaWan/etc) = **contexto, não prova** (consenso user+3 IAs).
- Nexo US fraco ($45.5k Coinbase) — reavaliar base de jurisdição CFTC.

**Queries Dune:** 7783641, 7783652, 7783674, 7783697, 7783717. Scripts: `_genius_reconcile.py`,
`_genius_eth_side.py` (NUNCA para GitHub).

---

## 🔴🔴 CAUSA-RAIZ — porque o dossier Gate/Bybit (11 casos, "$167M") está errado (23 Jun 2026)

Testados a fundo GENIUS, SWARMS, GOAT — os três falham. Causa-raiz identificada e GENERALIZÁVEL:

**O Arkham `/transfers` avalia memecoins de baixo preço a ~$1,00/token.** O dossier leu `unitValue`
como USD → cada número inflacionado 10-100x conforme o preço real.

Exemplo SWARMS (prova): hub `G8ukEc` recebeu 58,946,650 tokens "swarms" (mint `74SBV4z...pump`).
- Arkham/dossier: **$58.7M** (= 58.9M × $1, errado)
- Dune com preço real ($0.1347): **$4,683,057** (12.5x inflado)
- Saída alegada "hub→Gate $46.7M": **$0 em Arkham E Dune — NÃO EXISTE** (perna assumida, não verificada)

**Confirmações:**
- SWARMS: listing foi Jan 2025 (dossier dizia 2026); token movido nem é o SWARMS real (é copycat pump).
- GOAT: aggregator `7X6QGov` vazio na janela do listing.
- Endereços do dossier são **token accounts (ATAs)**, não owners — filtrar por `to_token_account`/
  `from_token_account` no Dune, OU por owner conforme o caso.

**Lição:** a submissão antiga não era "fraca" — estava numericamente errada por ordem de magnitude.
Qualquer caso futuro tem de ser reconstruído de raiz: preço real (Dune `amount_usd`, não Arkham
`unitValue`) + perna de saída verificada para CEX deposit com label. Sem isso, não submeter.

Queries: 7783928/46/70/73/83/93/98, 7784003/09/49.

**O BUG AFETA TODA A WATCHLIST BSC, não só o dossier.** Teste (23 Jun): a "maior insider"
`0x016b7836` (rotulada "125.9M GAIN") recebeu em stablecoin real desde 2025 apenas **$60,000 USDT**
(2 txs). Os "$35M/44M/47M/125M GAIN" das camadas 3 do NOTES são todos o mesmo artefacto Arkham.
Contraste: GENIUS teve $280k stablecoin REAL (swap atómico 22 Jun). **UPGRADE DO MOTOR:** ordenar
candidatos por USDT/USDC líquido recebido (Dune), NÃO pelo label USD do Arkham. Isso separa real de
fantasia automaticamente. Query teste: 7784182.

---

## 🗺️ MAPA DA REDE COMPLETA BSC — Diagrama de Consulta (Jun 2026)

> Ler como: `→` = envia tokens/USDT para. Endereços completos sempre que conhecidos.
> Estado: ✅ activo | ⏸️ parou | ❓ identidade pendente | ❌ resolvido/fechado

---

### 🏁 ESTADO FINAL HONESTO — Jun 17 2026

**MORTO (teses refutadas):**
- "Prime broker OTC clandestino" → era Gate.io Hot Wallet (`0x0d0707`).
- "Main accumulator" → era um MEV Bot de arbitragem (`0x055a3b37`).
- "Tudo converge para Binance Treasury" → o nó central era PancakeSwap Vault (`0x238a358808`).
- "Exchanges (Binance/Gate/OKX) em esquema ilegal de compra/venda entre si" → falso; são
  hot/cold wallets, MEV bots e routers DEX a operar normalmente.
- Todos os IDs por brand-spam (Binance/OKX) → falsos. Bitget, LBank, PancakeSwap nos lugares.

**O ÚLTIMO FIO — TESTADO E FECHADO Jun 17 (sybil test):**
- A "cascata ordenada decrescente" do dump VELVET Jun 12 (109 wallets, 1 tx cada, 16:39→16:43,
  montantes em ordem decrescente) parecia um script de operador único.
- TESTE: quem financiou o gas das 109 wallets? → `0x6596da8b65995d5feacff8c2936f0b7a2051b0d0`
  financiou 85/109. MAS esse mesmo endereço financiou **313,183 wallets** que depositam USDT na
  Gate → é a **ESTAÇÃO DE GÁS DA GATE.IO**, não um operador de dump.
- INTERPRETAÇÃO CORRECTA: as 109 wallets são **deposit addresses da Gate.io**; a "cascata
  ordenada" é a **Gate a varrer depósitos** para a hot wallet por ordem de saldo. Script da
  Gate, não de insider.
- VEREDICTO: on-chain NÃO há caso de insider. O que restaria — saber se as deposit addresses
  pertencem à mesma entidade (contas múltiplas Gate) — está atrás do KYC da Gate, invisível
  on-chain. Só um regulador com subpoena lá chega.

**Conclusão final:** a investigação deu (1) um mapa de infra BSC correcto e verificado, (2) uma
metodologia validada (só labels Arkham, nunca inferência/spam/fluxo), (3) confirmação de que NÃO
há crime detectável com dados públicos. Resultado honesto: tese refutada em todos os níveis.

---

### 🔴🔴 REFORMULAÇÃO FUNDAMENTAL — Jun 17 2026 (Arkham UI) — LER PRIMEIRO

A verificação dos nós centrais no Arkham UI desmontou a tese do "prime broker OTC clandestino".
Identidades REAIS dos nós que julgávamos ser uma rede secreta:

| Nó | Tese antiga (ERRADA) | Identidade Arkham (real) |
|----|----------------------|--------------------------|
| `0x0d0707963952f2fba59dd06f2b425ace40b492fe` | "Prime Broker OTC secreto" | **Gate.io Hot Wallet** |
| `0x055a3b37957bfbd3345bed9968e7e8dd56d67066` | "Main Accumulator" | **MEV Bot** (arbitragem) |
| `0xc882b111a75c0c657fc507c04fbfcd2cc984f071` | "Gate.io OTC Desk" | **Gate: Cold Wallet** (era Gate ✅) |
| `0x238a358808379702088667322f80ac48bad5e6c4` | "Binance BSC Treasury" | **PancakeSwap Vault** |
| `0xb300000b72deaeb607a12d5f54773d1c19c7028d` | "vault Binance $1.04B" | **Binance Wallet: DEX Router** |
| `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` | "PancakeSwap pool?" | **Binance Wallet: Proxy (1967 Transparent)** |
| `0x3bc367866468d4f80096be899b66ab29d03f2717` | "OTC Hub multi-exchange" | **Custom Proxy** (contrato) |
| `0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23` | "Binance mega hub" | **Bitget** infra |
| `0xb7697d225fa34bf1ebd3413adfa1c35b1be74729` | "Settlement Hub $2B" | sem label (vazio) |
| `0x218c18d02f0723291ce93aa5c0e5eb709903179a` | "Market Making Engine" | sem label |
| `0x286da956` / `0x98445c3a` / `0x031942f2` | "infra Binance $1B+" | vazios / $0 |

**O que isto significa:** o que mapeámos como "sellers insiders → prime broker → accumulator →
Binance Treasury" é, na infraestrutura real: **utilizadores a depositar tokens na Gate.io Hot
Wallet → um MEV bot de arbitragem → routing por DEX (PancakeSwap) e wallets DEX da Binance.**
Os "198 senders de SIREN ao broker" = 198 utilizadores da Gate.io a depositar, não uma rede
coordenada secreta. A espinha dorsal é Gate.io + MEV bot + PancakeSwap + Bitget + Binance DEX infra.

**O que ainda PODE ter valor (a re-avaliar, não assumir):** o padrão de wallets que tocam os
mesmos 7 tokens pré-listing e vendem em janelas curtas pode ainda indicar traders coordenados —
MAS a "infra de broker" que os ligava era afinal a Gate.io. Reconstruir a tese a partir dos
labels confirmados, sem assumir conspiração onde há só fluxo de exchange/arbitragem/DEX.

⚠️ Tudo o que se segue no mapa foi escrito ANTES desta reformulação — ler com este filtro.

---

---

### CAMADA 0 — APEX DE CAPITAL (Infra de Exchanges)

> ⚠️ CORRECÇÃO CRÍTICA Jun 17 (Arkham API): o brand-spam fingerprint estava ERRADO.
> O spam de marca é controlado pelo EMISSOR — qualquer um envia "币安/Binance" para qualquer
> endereço. Os labels de ENTIDADE do Arkham (arkhamEntity) é que mandam. Re-verificar tudo
> que foi classificado só por spam. Ver REGRAS no fim.

```
[BITGET BSC MEGA HUB — $40.2B USDT, ~15k txs/dia]
0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23  ✅ BITGET infra (CONFIRMADO Arkham Jun 17) — NÃO Binance!
    │  Arkham: inbound $50.6B de Bitget main 0xffa8DB7B + centenas de "Bitget Deposit"
    │  Arkham: outbound $50B+$27B para wallets Bitget (0xaDFffc33, 0x26209d9f, 0x70213959)
    │  cluster (ambas direcções) = 100% Bitget. Hot/omnibus wallet Bitget BSC.
    │  envia também p/ Binance/OKX/Kraken/Coinbase Deposit = settlement inter-exchange normal
    │  (o "fingerprint Binance" anterior era spam falso — METODOLOGIA REJEITADA)
    ├──→ 0xbcf60111...  [relay $18M Jun 14-16]
    │       └──→ Main Accumulator 0x055a3b37 (via VELVET: 195 txs)
    └──→ 0xfe05e140...a52c  [pass-through]
            └──→ 0x1ab4973a (cicla de volta — confirmed loop)
    NOTA: continua a alimentar o broker (apex de capital), mas é Bitget, não Binance.

[PANCAKESWAP VAULT — $1B+ USDT]  ❌❌ CORRECÇÃO CRÍTICA Jun 17 (Arkham UI)
0x238a358808379702088667322f80ac48bad5e6c4  = PANCAKESWAP VAULT, *NÃO* Binance BSC Treasury!
    │  ⚠️ Toda a investigação dizia "tudo converge para Binance Treasury" — ERRADO.
    │  Este nó central é o vault do PancakeSwap (DEX). A rede OTC LIQUIDA/VENDE os tokens
    │  pré-listing em LIQUIDEZ DEX (PancakeSwap), não deposita na tesouraria Binance.
    │  Reinterpretar: market makers → PancakeSwap = swap/venda on-chain, não settlement Binance.
    ├──→ 0xb300000b72deaeb607a12d5f54773d1c19c7028d  [= Binance Wallet: DEX Router ✅ Arkham Jun 17]
    ├──→ 0x286da956... / 0x98445c3a... / 0x031942f2...  [SEM label / $0 no Arkham — não são "infra Binance"]
    └──→ + outros wallets (a maioria sem label)
    NOTA: dos downstream, só 0xb300000b (Binance DEX Router) e 0x73d8bd54 (Binance Proxy) têm
    label Binance — e são infra DEX/proxy, não tesouraria. Os restantes estão vazios.

[OTC CROSS-EXCHANGE DESK — $1.39B bilateral, 1.79M txs]
0xe0f0aa98b4a4d305ac4a04d830c96a158bda9cd8  ✅ OTC desk cross-exchange (CONFIRMADO Arkham Jun 17)
    │  Arkham INBOUND: dominado por LBank Deposit (~$60M, dezenas de wallets LBank)
    │  Arkham OUTBOUND: Binance Deposit (maioria) + MEXC Deposit + Gate Deposit
    │  → arbitragista/OTC que move liquidez LBank → Binance/MEXC/Gate E alimenta o broker
    ├──→ 0x0d0707 (Prime Broker): 2 txs USDT, $666,527  ← financia o broker
    └──→ 0x055a3b37 (Main Accumulator): 1 tx USDT, $6,999  ← financia o accumulator
    Top sender: 0x4e7218ee (= LBank Deposit, ver correcção na Camada 2)
```

---

### CAMADA 1 — PRIME BROKER OTC

```
[GATE.IO HOT WALLET — antes "Prime Broker"]  ❌ CORRIGIDO Jun 17 (Arkham UI)
0x0d0707963952f2fba59dd06f2b425ace40b492fe  = GATE.IO HOT WALLET (não broker secreto!)
    │  os "100+ sellers" = utilizadores da Gate.io a depositar tokens (fluxo de exchange normal)
    │  o "recrutamento com BNB gas" = Gate.io a fornecer gas a deposit addresses (rotina exchange)
    │  "novo token com 5+ senders" ainda pode sinalizar interesse, mas NÃO é conspiração de broker
    ├──→ 0x055a3b37957bfbd3345bed9968e7e8dd56d67066  [= MEV Bot, não "accumulator"]
    ├──→ 0x3bc367866468d4f80096be899b66ab29d03f2717  [= Custom Proxy, contrato]
    ├──→ 0x218c18d02f0723291ce93aa5c0e5eb709903179a  [sem label Arkham]
    └──→ 0x0668b4d29bf7609d0e8dccd81061801728e64623  [Satellite — re-avaliar]
```

---

### CAMADA 2 — SETTLEMENT E DISTRIBUIÇÃO

```
[MEV BOT — antes "Main Accumulator"]  ❌ CORRIGIDO Jun 17 (Arkham UI: "MEV Bot")
0x055a3b37957bfbd3345bed9968e7e8dd56d67066  = MEV BOT de arbitragem (não "accumulator")
    │  $1.52M portfolio (BSC-USD, WBNB, USDC, USD1, PIT, NAWS, PIG); OpenSea user
    │  Exchange usage: Binance 31%, Gate 22%, MEXC 17%, Bitget 13%, Bybit 10%, KuCoin 5%
    │  Counterparties: Uniswap V3, PancakeSwap V3, KuCoin HW, Bitget HW, 0xb7697d225fa
    │  → bot que arbitra tokens entre TODAS as exchanges + DEXs. "Acumular tokens" = inventário de arb.
    ├──→ 0xb7697d225fa34bf1ebd3413adfa1c35b1be74729  [sem label — provável infra MEV/arb]
    ├──→ 0xc882b111a75c0c657fc507c04fbfcd2cc984f071  [= Gate: Cold Wallet ✅ confirmado]
    └──→ wallets diversas (re-avaliar — não assumir "insiders")

[0xb7697d225fa — antes "Settlement Hub $2B"]  sem label Arkham (vazio)
0xb7697d225fa34bf1ebd3413adfa1c35b1be74729  ❓ sem label; counterparty do MEV bot
    └──→ 0x238a358808 = PancakeSwap Vault (DEX)

[0x218c18d0 — antes "Market Making Engine"]  sem label Arkham
0x218c18d02f0723291ce93aa5c0e5eb709903179a  ❓ sem label (opera QAIT, SIREN, BTW, 20+ tokens)
    └──→ 0x238a358808 = PancakeSwap Vault (vende/swap on-chain DEX)

[0x3bc36786 — antes "OTC Hub"]  = Custom Proxy (contrato) [Arkham Jun 17]
0x3bc367866468d4f80096be899b66ab29d03f2717  = Custom Proxy (smart contract, não exchange)
    └──→ 0x238a358808 = PancakeSwap Vault (DEX)

[MARKET MAKER 2]
0x4a4915a0...  ✅
    ├──→ 0x4e7ed91e702ef2ff0c58e251c6e20d1dc1e31a5f  [❌ NÃO É OKX — CONFIRMADO Arkham UI Jun 17:
    │       SEM label de entidade ("High Transacting" só). Trader/MM de PancakeSwap (counterparties
    │       = PancakeSwap Vault + V3 Pool). EXCHANGE USAGE = 100% BINANCE ($489K withdrawals),
    │       ZERO OKX. Portfolio: USDT/USDC/WBNB/SKYAI/ZEST/JCT/KGEN. O "OKX" era brand-spam falso.]
    │       └──→ 0x238a358808 = PancakeSwap Vault (174k txs — swaps DEX, não settlement Binance)
    ├──→ 0xce2213f4...
    └──→ 0xd5da17a8...

[GATE.IO OTC DESK]
0xc882b111a75c0c657fc507c04fbfcd2cc984f071  ✅ (timing 04:26 UTC = automático Gate.io)
    │  inventário actual:
    │    HANA:   70.7M net (245M in / 175M out) → listing iminente
    │    ESPORTS: 31.7M net (55M in / 23M out)  → listing iminente
    │    VELVET:  ~14.2M restante (liquidando em tranches 04:26 UTC)
    └──→ broker / mercado (venda progressiva)

[SATELLITE OTC]
0x0668b4d29bf7609d0e8dccd81061801728e64623  ✅
    │  handles: D (932txs/39M), XTER (439txs/6.8M), PARTI, AVL, EDU, LISTA, SOLV, HOOK
    └──→ clearing bilateral (recebe de broker, redistribui)

[BINANCE ALPHA REWARDS AGGREGATOR]
0xd2dd7b597...  ✅ (recebe diariamente 12:00-12:03 UTC de staking pools)
    │  tokens: ESPORTS, XTER, ASTER, PARTI, B2, ZBT, CAT, Cake, Cheems, $BANANA, XNY, COOKIE, M
    └──→ distribui para holders Binance Alpha

[LBank DEPOSIT — corrigido Jun 17]
0x4e7218ee69950f4822c7d7d981935e900ad00a39  ✅ LBank Deposit (CONFIRMADO Arkham Jun 17)
    │  ❌ NÃO é "Binance Chinese OTC desk" (classificação anterior errada por brand-spam)
    │  net-zero router de VELVET (IN 370,241 = OUT), $102M USDT bilateral
    └──→ é a fonte principal do OTC desk 0xe0f0aa98 (LBank → arbitragem)
```

---

### CAMADA 3 — INSIDERS CORE (OTC Sellers)

```
[4 INSIDERS CORE — script sincronizado, venda em janela de 20s]
Todos os 4 têm acesso a TODOS os tokens pré-listing (7/7):

0x24a0d9928a3b6cd13a6210d0ff6d450a080fc266  ✅ 7/7 tokens, 128 txs, 35.8M GAIN
    └──→ 0x0d0707 (Prime Broker)

0xb85b098448b2aac4af96f5bdd9c6c02373a08975  ✅ 7/7 tokens, 128 txs, 44.7M GAIN
    └──→ 0x0d0707 (Prime Broker)

0x8d17fbfb03a6b7e8fdcfd60f1f9e6c08578ba5d7  ✅ 7/7 tokens, 117 txs, 47.8M GAIN + 10.3M QAIT
    └──→ 0x0d0707 (Prime Broker)

0xe6451016f095835a0d5ef98a5c0092e47ddf0a93  ⏸️ 7/7 tokens, 116 txs, 31.8M GAIN — PAROU Mai 4 2026
    └──→ 0x0d0707 (Prime Broker)

[GAIN OTC SELLERS — confirmados Jun 13]
0x016b7836331b7d0026dd99cf903bfcad41e1a189  ✅ 125.9M GAIN (maior de todos)
    └──→ 0x0d0707
0x96973f7b83a3c785d94e0a6d8712174abb81b748  ✅ 21.3M GAIN + 24M QAIT (activo Jun 13)
    └──→ 0x0d0707

[INSIDERS 6/7 TOKENS]
0xfb9bf2dde6dcdc44d3b89ddb477f8503a3b9d0bb  SIREN/VELVET/XTER/TOWN/WARD/HANA  69 txs
0x89e94acc3a619fbea6aa28c26eec8b6f01e2ac8b  WARD/HANA/SIREN/TOWN/VELVET/ESPORTS  49 txs
0xb2655ac91bb3536bcfa0993069da6affabadc33d  SIREN/VELVET/HANA/XTER/TOWN/WARD  31 txs
0x98f870ab30c0530b2e19d1adf5285200f52305a7  WARD/TOWN/XTER/VELVET/HANA/ESPORTS  27 txs
0xce0a9664b28d28062fe59a03f34a5c855bc10570  XTER/TOWN/WARD/SIREN/VELVET/HANA  23 txs

[INSIDERS 3 TOKENS — SIREN+HANA+ESPORTS confirmados]
0x6cdf94520d00ef13b9b56f3815107b9529b8957b  — entrada SIREN Mar 21 2025 (a mais antiga)
0x33ba873aa26b9c44c311e44bfd502dc7ad9cda8a  — alta actividade em todos
0xdd04f596569b09bb967ab9f20cdc1b7bc7495afd  — 70+ txs SIREN
0xbc0be9e090224983eb9bff63eb9504dd55994e17  — HANA 59.7M + ESPORTS 2.5M
0x9e4a7a68e6b94f852f60f5eaf1c505e37d2e7d35  — vendeu SIREN+ESPORTS mesmo dia Jun 3
0x41cd20a8871176893090fcf29412e6d9fbcffe20  — vendeu SIREN+ESPORTS mesmo dia Jun 3
0x2004b06ea7c2f5eec504ec8489ec210dfe220fd5  — vendeu SIREN+ESPORTS mesmo dia Jun 3

[AGREGADORES VETERANOS INDEPENDENTES — não sincronizados com script]
0xea6d0eb93b28ea690c6d26820b392d4e4868338d  40+ tokens desde Jan 2025 — "antena" do broker
    └──→ vende ao broker mas 66s fora da janela core — NÃO faz parte dos 4 insiders
0x744727a6...  40+ tokens desde Jan 2025 (memecoins → tokens Alpha)
0xe92bd58a...  30 tokens desde Feb 2025, DKS 454M, BLUAI 138M, HANA 72M
```

---

### CAMADA 4 — SUPPLY POR TOKEN

#### VELVET (Velvet Capital DeFAI)
```
Contrato: 0x8b194370825e37b33373e74a41009161808c1488

0x579d36cc...  [deployer — mintou 1B Jul 9 2025]
    ├──→ 0x6bff1c3e...  [VC #1 — 72.7M = 7.27% supply]
    │       └──→ 0x150c8a0aff9caefe3ce92658afa302e0172d1056  [redistributor Jun 6-7]
    │               └──→ 7 wallets frescas
    │                       └──→ 109 wallets dump Jun 12 16:39 UTC → -52% crash
    ├──→ 0xe2e8fa23dda79231e4bd237321fd843fd7e9e0a7  [VC #3 — 35M PARADOS]  ⚠️ DUMP PENDENTE
    └──→ 0xcf990fa3...  [team vesting — 645M, desbloqueia progressivamente]

Top holders VELVET:
  0x6e0bad2c077d699841f1929b45bfb93fafbed395  471M (645M in, 173M out)
  0x75e7488ac067f07948739bfb550213b47db094bb  160M (zero outflows)
  0xd19dce537125dfb5e76d7131668c4d5e4172b56c  107M (bilateral = exchange)
  0xe2e8fa23dda79231e4bd237321fd843fd7e9e0a7   35M (zero outflows — ⚠️ dump pendente)
  0xc882b111 (Gate.io)                         ~14.2M restante (liquidação em curso 04:26 UTC)

Wallets redistribuídas Jun 15 (acumulação para próximo dump):
  0x4e7218ee69950f4822c7d7d981935e900ad00a39  ~210k (net-zero router)
  0x03631c388fb01e0d929627b614eeb501c0ef9dce   50.6k
  0xe48ebd633200108085ab7413d38af7ac894bcb65   38.7k
  0xc9dfb45265ba3e312d4fbb7ee6effafcc85ddad3   14.1k
  0x7dd17204b864d1a3599b8b206b5d985b46c761ef   ~13k (também recebe HANA)

30 wallets recrutadas Jun 15 com BNB gas — SEM TOKEN AINDA (monitorizar):
  0xb7d79c2937e2cbf310ac14d68e81df40c59ac122  | 0x26ce83b97dba85c888be7765091692786bd49df0
  0xdb6b2f89e86487a35d8796e500a6ea81c8af9997  | 0xb7e99b4d3c40ca8b1b0de34fd3a723b4b2c3508d
  0x54f64ef6694e1f633176cdce73143d1f23cb439d  | 0xae72c8c11cf624399c202ea4b707227e2a852533
  0xed54d77e909a97765cf1099a9ad51926cd97d43d  | 0xe315fac9b25718c3a8bae46bbf7558828830fa48
  0xb9f519362ea80e3c60df7d43644d8ae857abde1e  | 0xf72adb50bd37b6270bdc287b993e6ebed9ee3a10
  [+ 20 adicionais — ver Entity 52 em 1.txt]
```

#### HANA (Hana Network)
```
Contrato: 0x6261963ebe9ff014aad10ecc3b0238d4d04e8353

Top holders HANA:
  0x483d66b57c64b6b4c80a0b37932814d1d6edcd25  411M (team/vesting confirmado)
  0x73d8bd54f7cf5fab43fe4ef40a62d390644946db  260M (bilateral — DEX/AMM PancakeSwap)
  0x06bdbdcaa165b8ddce5384fbad4b0365cbad8d9e   80M (pure holder, zero outflows)
  0xc882b111 (Gate.io)                          70.7M (inventário, listing iminente)

Outlet activo:
  0x7dd17204b864d1a3599b8b206b5d985b46c761ef  recebeu 34.5M HANA Jun 9 — intermediário cluster VELVET-HANA-LAB-GAIN
      └──→ NÃO é 6º membro core (hipótese refutada Jun 16)

Strategic holder (PAROU):
  0xe97b1f053c9118041c9016d83c86deffbf398095  SIREN 15.7M + VELVET — PAROU (igual padrão SIREN antes de crash)
```

#### ESPORTS (Yooldo Games)
```
Contrato: 0xf39e4b21c84e737df08e2c3b32541d856f508e48

Top holders ESPORTS:
  0x49a0c2366936b115d6877438175ee4b97d6dab7c  240M (team?)
  0x99d4b3f50b14bfc67892c472f4053ee3483d87b9  212M (staking pool oficial ESPORTS)
      └──→ 97.9M → 0xd2dd7b597 (Binance Alpha rewards aggregator, fees diárias 12:00 UTC)
  0x73d8bd54...                               128M (bilateral DEX/AMM)
  0xbcc2b854...                                35M (holder estático)
  0xc882b111 (Gate.io)                         31.7M (inventário, listing iminente)

Pass-through:
  0xb7f68f5f2fb7f1e4cfe6b513cb1b5fbc08ef1d61  recebeu 19.9M de redistribuidor
      └──→ 0x99d4b3f5 (tudo reencaminhado)
```

#### TOWN (Alt.town)
```
Contrato: 0x1aaeb7d6436fda7cdac7b87ab8022e97586d2da1

Top holders TOWN (⚠️ alta concentração):
  0x2064e723bbf590bfe3f4b72c91a570ad469cb5af  380M (~38% supply) ← ALTO RISCO
  0x6a3b5276c23dbf1834c8d06433b312e408b1f9f6  300M (~30%, zero outflows = team/lock?)
  0xdb435a0cca19df36a82e2fd19fe0ee58d71c7a03  170M
  0x73d8bd54 (DEX/AMM)                         170M (bilateral pool)
  0x48d9cf74639d9a70ed9144f42e6f260a0b5e6df3  130M (estático)
  [Top 2 = 680M / ~1B supply = 68% — risco dump moderado-alto]
```

#### DARK (Dark Eclipse)
```
⚠️ 2 CONTRATOS DISTINTOS:
  Contrato 2021: 0x12fc07081fab7de60987cad8e8dc407b606fb2f8 ($100k MC, 250M supply original, remints)
  Contrato 2025: 0xb05f4747eb3d18a3fa4aa3e5c627f02ccc70d005 (criado Jun 27 2025, 1B supply)

Redistribuidores (usam contrato 2021):
  0xdca693422fac1e15341c3cede40a1798ee7af4b3  [central — 115 wallets, 6125 txs, 465M distrib] ✅
  0xa3c96072e43eff455b11a27bbc332a23579d77f3  [secundário — 146 wallets, fluxos 2025 também] ✅
  0xb300000b (Binance vault)                   distribui AMBOS contratos → 14 wallets + 0x1231deb6
  0x28e2ea090877bf75740558f6bfb36a5ffee9e9df  OTC partner (GENIUS+SIREN) → 74 wallets DARK 2021
  0xc2eff1f1ce35d395408a34ad881dbcd978f40b89  acumulador DARK 2025 (~970k Jun 15, novo)

Os 7/7 insiders core acumulam DARK 2021 desde Mai 5:
  0x8d17fb (43M) | 0xe64510 (41M) | 0xb85b09 (40M) | 0x24a0d9 (35M) e todos os outros
```

#### SIREN (sinal — JÁ CRASHOU -90%)
```
Redistribuidor central:
  0x53f78a071d04224b8e254e243fffc6d9f2f3fa23  [377 wallets SIREN, 6 dump wallets Beat] ✅
      Feeders activos Jun 13 2026:
        0x8dac80ce...  47.9M (activo Jun 8)
        0x9021069c88b4cb6cdad09d6f01b56e8282fcb19  36M (2,549 txs, activo Jun 13) ✅
        0xb8e6d31e7b212b2b7250ee9c26c56cebbfbe6b23  35M (activo Jun 9) [endereço recuperado]
        0x39ac22b2063b9c64a4fc2d00b26cccc5271bd31b  29.8M (activo Jun 13) ✅
        0x9f2fa854...  24.7M (activo Jun 13)
        0xac474892...  20M (activo Jun 13) — ⚠️ ENDEREÇO TRUNCADO, não recuperado
        + 4 feeders menores

Strategic holder (parou):
  0xe97b1f053c9118041c9016d83c86deffbf398095  15.7M SIREN (parou antes do crash)
```

---

### CAMADA 5 — NÓS PASS-THROUGH / RELAY (resolvidos)

```
0xe9f1c1a3...  NET-ZERO (IN $3.127M = OUT $3.127M) — ❌ não é staging parado
    ├──→ $1M → 0x128463...
    └──→ $2.13M → 0xfe05e140...a52c → 0x1ab4973a (ciclo confirmado)

0x4e7218ee... (VELVET)  NET-ZERO router — IN 370,241 = OUT 370,241 — ❌ não é dump risk

0x7dd17204b864d1a3599b8b206b5d985b46c761ef  cluster VELVET-HANA-LAB-GAIN circular
    → recebe e envia os mesmos 4 tokens — intermediário, NÃO insider core

DEX/AMM HUB:
0x73d8bd54f7cf5fab43fe4ef40a62d390644946db  PancakeSwap pool / BSC DEX aggregator
    → bilateral em SIREN (890k txs!), TOWN, FIGHT, BULLA, RIVER, memes — infra de mercado
```

---

### CAMADA 6 — INVESTIGAÇÃO GENIUS (Arkham API, paralela)

```
[gianmarco_eth — operador GENIUS]
0xD8BDd80BBc4d874702...  [acumulador principal, label "gianmarco_eth"]
    ├──→ $2.375M → 0x9d9695C225D566D778...  [PROFIT PARADO desde listing Mai 2026] ⚠️ monitorizar
    └──→ $2.786M → 0x0eF2fb1a748937d780...  [relay → deBridge cross-chain]

Hub/fonte:
  0x199A7443a80ab606f7...  recebe de LiquidMesh proxies → alimenta gianmarco_eth
```

---

### ENDEREÇOS PENDENTES — INVESTIGAÇÃO EM ABERTO

```
⚠️ 0xe0f0aa98b4a4d305ac4a04d830c96a158bda9cd8  — RESOLVIDO Jun 17: OTC USDT LIQUIDITY PROVIDER
    Endereço completo recuperado. $1.39B USDT bilateral, 1.79M txs totais.
    Envia USDT directamente ao Prime Broker (2 txs, $666k) e Main Accumulator (1 tx, $7k).
    → É o FORNECEDOR DE LIQUIDEZ USDT da rede OTC — financia o broker para comprar tokens.
    Spam misto: BinanceAI + BinanceDance + VIP828欧易最高折扣码 (OKX) → intermediário neutro,
    não infra de uma única exchange. Também vítima de address poisoning (UṢDT x16).
    Próximo passo: Arkham fingerprint para identidade exacta.

✅ 0xe97b1f053c9118041c9016d83c86deffbf398095 — RESOLVIDO Jun 17 (Arkham): TRADER MULTI-EXCHANGE BASE BITGET
    Aparece em SIREN+VELVET no cross-listing (cross-destination). Recebe de: Bitget hot wallets
    (0x1AB4973a = Bitget apex, +5 Bitget deposit addrs), PancakeSwap, Gate. Envia para: Gate
    Deposit, Bitget Deposit, Binance Deposit, PancakeSwap. Volume total: $6.9M in / $8.1M out.
    Identidade: trader BSC activo com Bitget como exchange principal. Aparece em múltiplos
    scans por amplitude de portfólio, não por acesso privilegiado. Thread encerrada.

✅ 0x218c18d02f0723291ce93aa5c0e5eb709903179a — RESOLVIDO Jun 17 (Arkham): GATE.IO OPERATOR BSC
    Arkham só vê $141k USD (BNB para gas). Financiado por Gate Hot Wallet. Envia para 0x7ccdB15F
    (desconhecido, provavelmente cold storage do mesmo operador Gate). Volumes reais de tokens
    BSC não indexados no Arkham (QAIT, SIREN, BTW são tokens baixo valor-USD). Conclusão:
    wallet de operações BSC da Gate.io. Sem ligação a insiders. Thread encerrada.

✅ 0xb7697d225fa34bf1ebd3413adfa1c35b1be74729 — RESOLVIDO Jun 17 (Arkham): MEV BOT PROFIT WALLET
    Recebe $200M do MEV Bot 0x055a3b37 (351 txs) + $19M PancakeSwap. Envia para: Bitget ($10M),
    Binance ($3.3M), Bybit ($2M), MEXC ($2M), Gate ($1.3M), KuCoin ($0.2M), PancakeSwap (bulk).
    É o treasury de saída do MEV Bot — liquida os lucros de arb em múltiplas exchanges.
    Sem ligação directa à rede prelisting. Thread encerrada.

⚠️ 0xe2e8fa23dda79231e4bd237321fd843fd7e9e0a7 — ACTIVO JUN 17: 35M VELVET AINDA PARADOS
    Verificado Jun 17: 1 inbound ($35M de 0xcd57107c = VC#3), ZERO outbound. Dump NAO aconteceu.
    ALERTA MANTIDA: segunda onda de dump VELVET pendente quando este wallet mover.

✅ 0x93deb693d1a4e9b17d6826e3afb35a455553f7e9 — VERIFICADO Jun 17: zero no Arkham (só tokens).
    32M VELVET recebidos de VC#4 (0x029d7bd5) em Jul 2025. Arkham não indexa — token low-price.
    Monitorizar on-chain se VELVET listar na Binance. Baixa prioridade.

✅ 0xcf990fa3a808c9aa68f2b1ab2f3476f6fed0bc4c — VERIFICADO Jun 17: zero no Arkham (contrato).
    Contrato de vesting team (645M VELVET). Não indexado por Arkham (tokens, não USDT).
    Monitorizar desbloqueios se VELVET listar. Baixa prioridade.

❌ 0xac474892...           SIREN feeder 20M — IRRECUPERÁVEL (SIREN usa eventos não-standard,
    zero rows em tokens.transfers E bnb.transactions). Thread encerrada Jun 17.

❌ 0x8a289d458f5a134ba40015085a8f50ffb681b41d — FORA DE ÂMBITO (fechado Jun 17, confirmado UI).
    Arkham UI: label "NegRiskCtfExchange" (CINZENTO = não confirmado; contrato tipo Polymarket).
    Faz parte de um anel DeFi de alta frequência com 0x41dce1a4 (sem label) e 0xcfb9bef5
    (= token contract "Wrapped Collateral / WCOL", interage com Venus Protocol vUSDT). Ou seja
    o "anel $2.52B" é INFRA DEFI DE COLATERAL/LENDING (Venus Protocol), NÃO sweep de depósitos.
    Ligação ao 0x6cfc3fd9 (razão do flag) é trivial ($332k, net ~$8k). ZERO ligação à rede
    pré-listing. Encerrado em definitivo.

✅ 0x3fe7b866182aab8c805769747663b3046541c4d6 — RESOLVIDO Jun 17: MARKET MAKER Binance BSC.
    Bilateral massivo com 0x144d395b (par MM). Recebe de Binance Treasury 0x238a358808
    (Beat/IRYS/MITO/USDT/OPG, 58k+ txs) e do OTC Partner 0x28e2ea09 ($65.8M USDT).
    Envia VELVET/Beat/OPG/IRYS p/ Binance Treasury. = engine de market making ligado à Binance.

✅ 0x144d395b5562c742259932d2ee6e1d8d092a21b8 — RESOLVIDO Jun 17: MM/DEX aggregator de topo.
    Destinos: 0xa50c4fe8c8a0a47872c378c11cf7f6ea1780ff7b ($718M USDT + $215M USDC + 30M UP —
    CONFIRMA o endereço completo correcto que estava marcado "malformado"!), 0x452244f59
    ($109M USDT + BULLA/FF/$BANANA/BTCB/ETH), 0x723508dd ($327M). Par bilateral de 0x3fe7b866.

✅ 0xeccbb861c0dda7efd964010085488b69317e4444 — RESOLVIDO Jun 17 (BscScan): token 龙虾 (LOBSTER),
    meme chinês, 1B supply, 8,795 holders. Não é wallet nem relevante. Thread fechada.

Convergência: rede toca Bitget (0x1ab4973a), Binance (Treasury/MM), LBank (OTC desk), Gate.io.
```

---

### REGRAS DE FILTRAGEM (anti-poison)

```
⚠️ ADDRESS POISONING: ignorar tokens com símbolos spoofados (" U5DТ ", "U឵S឵DΤ") e amount=0
REGRA: filtrar SEMPRE por contrato USDT real 0x55d398326f99059ff775485246999027b3197955
REGRA: verificar SEMPRE CoinGecko/CMC antes de classificar token como pré-listing
🚫 REGRA CRÍTICA (Jun 17): BRAND-SPAM FINGERPRINT É INVÁLIDO. O spam de marca (币安/欧易/Binance)
   é controlado pelo EMISSOR — qualquer um envia para qualquer wallet. NUNCA classificar uma
   exchange por spam recebido. Usar SEMPRE labels de entidade Arkham (arkham_wallet_trace.py,
   campo arkhamEntity). Casos afectados: 0x1ab4973a (era "Binance"→é BITGET), 0x4e7218ee
   (era "Binance OTC"→é LBank), 0x4e7ed91e (OKX por confirmar).
   NOTA: Arkham /transfers API só devolve dados para endereços que rastreia como entidade;
   wallets BSC de altíssima frequência (>400k txs) devolvem 0 — usar Arkham UI manual nesses.
```

---

## 🎯 WATCHLIST — SINAIS EM TEMPO REAL (para o programa)

> Formato: `address | token | chain | signal_type | notas`
> signal_type: `short_warning` | `listing_signal` | `new_token_alert` | `accumulating` | `profit_holding` | `supply_active` | `recruitment`

### VELVET
```
0xe2e8fa23dda79231e4bd237321fd843fd7e9e0a7 | VELVET | bnb | short_warning   | 35M parados desde Mar 4 — 1ª tx = dump incoming, short imediato
0xc882b111a75c0c657fc507c04fbfcd2cc984f071 | VELVET | bnb | short_warning   | Gate.io tem ~14.2M restantes — cada tranche ~04:26 UTC = pressão venda
0x4e7218ee69950f4822c7d7d981935e900ad00a39 | VELVET | bnb | accumulating    | Binance Chinese OTC desk ($102M USDT bilateral) — 210k VELVET Jun 15, liquida para Binance HW
0x150c8a0aff9caefe3ce92658afa302e0172d1056 | VELVET | bnb | short_warning   | redistribuidor original do dump Jun 12 — se activar de novo = novo evento
```

### HANA
```
0xc882b111a75c0c657fc507c04fbfcd2cc984f071 | HANA   | bnb | listing_signal  | Gate.io tem 70.7M — acumulação pré-listing; anúncio = pump
0xe97b1f053c9118041c9016d83c86deffbf398095 | HANA   | bnb | listing_signal  | strategic holder 158.9M — se vender = listing Binance Spot iminente
0x7dd17204b864d1a3599b8b206b5d985b46c761ef | HANA   | bnb | listing_signal  | outlet activo Jun 9 (34.5M HANA) — também recebe VELVET
```

### ESPORTS
```
0xc882b111a75c0c657fc507c04fbfcd2cc984f071 | ESPORTS| bnb | listing_signal  | Gate.io tem 31.7M — listing iminente
0xb7f68f5f2fb7f1e4cfe6b513cb1b5fbc08ef1d61 | ESPORTS| bnb | short_warning   | pass-through — recebeu 19.9M de redistribuidor, enviou tudo para 0x99d4b3f5
0x99d4b3f50b14bfc67892c472f4053ee3483d87b9 | ESPORTS| bnb | supply_active   | staking pool oficial ESPORTS (1276+ stakers) — envia fees diárias para Binance Alpha aggregator
```

### Rede insider 7/7 — qualquer token novo = próximo listing
```
0x24a0d9928a3b6cd13a6210d0ff6d450a080fc266 | *      | bnb | new_token_alert | 7/7 tokens Binance Alpha — novo token aqui = listing em semanas
0xb85b098448b2aac4af96f5bdd9c6c02373a08975 | *      | bnb | new_token_alert | 7/7 tokens Binance Alpha — mesmo padrão
0x8d17fbfb03a6b7e8fdcfd60f1f9e6c08578ba5d7 | *      | bnb | new_token_alert | 7/7 tokens Binance Alpha — mesmo padrão
0xe6451016f095835a0d5ef98a5c0092e47ddf0a93 | *      | bnb | new_token_alert | 7/7 tokens (parou Mai 4) — se reactivar = sinal forte
0x96973f7b83a3c785d94e0a6d8712174abb81b748 | *      | bnb | new_token_alert | 5/7 tokens, maior seller VELVET Jun 12 — ainda activo
```

### Gate.io Hot Wallet — depósitos de novo token podem sinalizar interesse (NÃO é broker secreto)
> ❌ CORRIGIDO Jun 17: 0x0d0707 = Gate.io Hot Wallet (Arkham UI), não "prime broker OTC".
> Sinal continua útil como proxy de actividade Gate.io, mas SEM a narrativa de conspiração.
```
0x0d0707963952f2fba59dd06f2b425ace40b492fe | *      | bnb | new_token_alert | Gate.io Hot Wallet — volume súbito de novo token = possível interesse Gate.io (não "broker")
0x0d0707963952f2fba59dd06f2b425ace40b492fe | BNB    | bnb | exchange_gas    | gas a deposit addresses = rotina de exchange (NÃO "recrutamento de dump")
```

### 30 wallets recrutadas Jun 15 2026 — sem token ainda (MONITORIZAR)
```
0xb7d79c2937e2cbf310ac14d68e81df40c59ac122 | ?      | bnb | recruitment     | gas Jun 15 15:04 — primed, sem token ainda
0x26ce83b97dba85c888be7765091692786bd49df0 | ?      | bnb | recruitment     | gas Jun 15 15:05 — primed, sem token ainda
0xdb6b2f89e86487a35d8796e500a6ea81c8af9997 | ?      | bnb | recruitment     | gas Jun 15 15:08 — primed, sem token ainda
0xb7e99b4d3c40ca8b1b0de34fd3a723b4b2c3508d | ?      | bnb | recruitment     | gas Jun 15 15:09 — primed, sem token ainda
0x54f64ef6694e1f633176cdce73143d1f23cb439d | ?      | bnb | recruitment     | gas Jun 15 15:14 — primed, sem token ainda
0xae72c8c11cf624399c202ea4b707227e2a852533 | ?      | bnb | recruitment     | gas Jun 15 15:18 — primed, sem token ainda
0xed54d77e909a97765cf1099a9ad51926cd97d43d | ?      | bnb | recruitment     | gas Jun 15 15:20 — primed, sem token ainda
0xe315fac9b25718c3a8bae46bbf7558828830fa48 | ?      | bnb | recruitment     | gas Jun 15 15:29 — primed, sem token ainda
0xb9f519362ea80e3c60df7d43644d8ae857abde1e | ?      | bnb | recruitment     | gas Jun 15 15:51 — primed, sem token ainda
0xf72adb50bd37b6270bdc287b993e6ebed9ee3a10 | ?      | bnb | recruitment     | gas Jun 15 16:56+17:35 — primed, sem token ainda
```
> AVISO: quando qualquer desta lista receber um token em volume = próximo dump. Monitorizar activamente.

### SIREN supply chain
```
0x9021069c88b4cb6cdad09d6f01b56e8282fcb19  | SIREN  | bnb | supply_active   | feeder activo Jun 13 (36M, 2549 txs) — quando parar = scheme a fechar
0x39ac22b2063b9c64a4fc2d00b26cccc5271bd31b | SIREN  | bnb | supply_active   | feeder activo Jun 13 (29.8M, 534 txs)
0x53f78a071d04224b8e254e243fffc6d9f2f3fa23 | *      | bnb | new_token_alert | redistribuidor cross-token (SIREN+Beat+GAFI) — novo token = novo dump
```

### DARK ⭐⭐⭐⭐ — acumulação broker (exchange desconhecida, confidence 6/10)
> **ATENÇÃO — 2 contratos DARK distintos no BSC:**
> - `0x12fc07081fab7de60987cad8e8dc407b606fb2f8` = DARK 2021 (Dark Eclipse, $100k MC, supply original 250M → redistribuidor já distribuiu 465M, logo houve remints)
> - `0xb05f4747eb3d18a3fa4aa3e5c627f02ccc70d005` = DARK 2025 (criado Jun 27, 2025; 1B supply; 1.55M txs — mais activo mas amounts menores no broker)
> Broker network toca em AMBOS. Confirmação pelo redistribuidor `0xdca693` → só usa contrato 2021.

```
0xdca693422fac1e15341c3cede40a1798ee7af4b3 | DARK   | bnb | new_token_alert | redistribuidor DARK 2021 (115 wallets, 6125 txs, 465M distrib) — drenar = dump
0xa3c96072e43eff455b11a27bbc332a23579d77f3 | DARK   | bnb | new_token_alert | redistribuidor DARK secundário (146 wallets) — também fluxos DARK 2025 (100k-900k)
0xb300000b72deaeb607a12d5f54773d1c19c7028d | DARK   | bnb | new_token_alert | Binance vault — distribui AMBOS contratos DARK; enviou para 0x1231deb6 (DARK 2025)
0x28e2ea090877bf75740558f6bfb36a5ffee9e9df | DARK   | bnb | accumulating    | OTC partner (GENIUS+SIREN) distribui DARK 2021 a 74 wallets + DARK 2025 a 0xc2eff1
0xc2eff1f1ce35d395408a34ad881dbcd978f40b89 | DARK   | bnb | accumulating    | acumulador DARK 2025 — recebeu ~970k tokens Jun 15 (novo, investigar)
```
> DARK 2021: todos os 7/7 insiders acumulam desde Mai 5 (146M+98M+64M+43M+41M+40M+35M). Redistribuidor `0xdca693` tem 115 wallets prontas.
> Confidence baixou 10→6/10: token de 2021 com $100k MC — provavelmente listing pequena exchange ou Binance Alpha, não Binance Spot.

### PZP ❌ JÁ LISTADO (Gate.io) — corrigido Jun 16 (não é pre-listing)
> Confirmado pelo utilizador Jun 16: "quanto ao pzp ja esta na gate sim". Mesmo erro que SAHARA —
> actividade do broker abaixo é market making pós-listing, não acumulação pré-listing.
> Contrato: `0xdce40c14d5956f8b8ba912402ba73b4d4d599612` (Out 3, 2024; 150M supply)
```
0xc923da27235094f8283aaac6b4a87bf8283fb41b | PZP    | bnb | new_token_alert | market maker PZP — recebe de redistribuidor 53f78a07 + 4982085c, drip-sell para 0x20c5b10
0x53f78a071d04224b8e254e243fffc6d9f2f3fa23 | PZP    | bnb | new_token_alert | redistribuidor cross-token (SIREN+Beat+GAFI+PZP) — 167M recirculados, activo hoje
0x4982085c9e2f89f2ecb8131eca71afad896e89cb | PZP    | bnb | new_token_alert | feeder para 0xc923da27 (143M PZP, activo hoje) — novo wallet
0x95ffb3a4b6764fb4549464c2677daed3c0e78b4e | PZP    | bnb | new_token_alert | destino 107.5M PZP (14507 txs) — possível pool DEX ou exchange
0x20c5b10046808c331e7aabf202b0c20ca526cc0b | PZP    | bnb | new_token_alert | destino final drip-sell de 0xc923da27 — DEX ou exchange feeder
```

### SAHARA ❌ JÁ LISTADO — market making (não pre-listing)
> Confirmado Jun 16: listado em Binance, OKX, Gate.io, Bybit, Upbit. Broker faz market making normal.
> Actividade broker (442M desde Jun 2025) = gestão de liquidez pós-listing, não acumulação pré.
> REMOVER da watchlist de pre-listing. Mesmo erro que PZP.

### FAR ⭐⭐⭐ — FAR Labs, candidato Binance Spot (VERIFICADO web Jun 16)
> Contrato: `0xc44f9f08e524669e5deeebc9eb142c81edfad178` = **FAR Labs** (AI/GameFi, distributed AI economy)
> **VERIFICADO CoinGecko Jun 16:** já listado em MEXC + BingX + Gate.io + PancakeSwap V3.
> MC ~$13.8M, preço $0.002835, rank #1004. NÃO está na Binance (nem Alpha nem Spot).
> Classificação correcta = "exchange upgrade" candidate (já tem mercado, aguarda Binance Spot),
> NÃO é new-token pre-listing. Confiança moderada: mercado já estabelecido = menos upside fácil.
```
0x055a3b37957bfbd3345bed9968e7e8dd56d67066 | FAR    | bnb | listing_signal  | Main Accumulator recebeu FAR (141k, Jun 15) — já em 3 CEX → candidato Binance Spot
0x218c18d02f0723291ce93aa5c0e5eb709903179a | FAR    | bnb | listing_signal  | Market Maker recebeu FAR (210k, Jun 15) — preparação possível Binance Spot
```

### FHE ⭐⭐⭐ — Mind Network, candidato Binance Spot (VERIFICADO web Jun 16)
> Contrato: `0xd55c9fb62e176a8eb6968f32958fefdd0962727e` = **Mind Network** (FHE / privacy AI, HTTPZ)
> **VERIFICADO Jun 16:** backed by Binance Labs + Chainlink + BytePlus. 1B supply, 351M circ.
> Já em ~24 exchanges (MEXC, Bitget, Bybit, Gate...) + **Binance Alpha** (NÃO Spot ainda).
> MC ~$8.5M, preço ~$0.0243. Token multichain (ERC-20 ETH + BSC).
> Classificação = candidato a upgrade Binance Alpha → Spot. Binance Labs backing reforça tese,
> mas mercado já maduro (24 exchanges) = não é pre-listing de token novo. Confiança moderada.
```
0x055a3b37957bfbd3345bed9968e7e8dd56d67066 | FHE    | bnb | listing_signal  | Main Accumulator recebeu FHE (19.7k, Jun 15) — Binance Alpha→Spot candidato
0x218c18d02f0723291ce93aa5c0e5eb709903179a | FHE    | bnb | listing_signal  | Market Maker recebeu FHE (8.3k, Jun 15) — preparação possível Binance Spot
```

### DN ⭐⭐ — DeepNODE (sinal REBAIXADO Jun 17 — era Binance Treasury, é PancakeSwap)
> Contrato: `0x9b6a1d4fa5d90e5f2d34130053978d14cd301d58` | Listado: Gate.io APENAS
> ❌ CORRECÇÃO: os 370M DN estão no PancakeSwap Vault (0x238a358808), NÃO na "Binance Treasury".
> 370M DN num vault DEX = LIQUIDEZ de pool PancakeSwap, não acumulação Binance pré-Spot.
> A tese "Binance listing iminente" perde força — é só liquidez DEX. Confiança ⭐⭐⭐⭐→⭐⭐.
```
0x238a358808379702088667322f80ac48bad5e6c4 | DN     | bnb | listing_signal  | PancakeSwap Vault (NÃO Binance) — 370M DN = liquidez DEX, não sinal Binance Spot [corrigido Jun 17]
0x055a3b37957bfbd3345bed9968e7e8dd56d67066 | DN     | bnb | accumulating    | Main Accumulator — 13.2M DN activo HOJE = pre-Binance Spot acumulação
```

### GENIUS — lucros parados gianmarco_eth (ETH) — SMART MONEY A SEGUIR ⭐
> Status Jun 17: AMBAS ainda paradas, zero saídas nos últimos 10 dias. Alerta Arkham criado/ a criar.
> Quando QUALQUER uma mover = gianmarco_eth a mexer no lucro = rasto fresco a seguir.
```
0x9d9695c225d566d77848c19f4728f62a5466e68a | GENIUS | eth | profit_holding  | 2.375M GENIUS parados desde Jun 9 (~$1.1M) — ALERTA: 1ª saída = sinal
0x0ef2fb1a748937d7800ffa143d5988aea2092241 | *      | eth | profit_holding  | relay/bridge gianmarco_eth $2.786M — ALERTA: qualquer tx = movimento do operador
0xe9f1c1a39ba8221a3ffe3a6bb41f943b3075892a | USDT   | eth | profit_holding  | $1.7M USDT staging parado — destino desconhecido, monitorizar
```

### Exchange HW downstream (OKX por confirmar)
```
0x4e7ed91e702ef2ff0c58e251c6e20d1dc1e31a5f | *      | bnb | listing_signal  | ⚠️ label OKX NÃO confirmado (vinha de brand-spam, metodologia rejeitada Jun 17) — verificar Arkham UI; novo token aqui ainda = sinal listing exchange
```

### Gate.io timing signal (universal)
```
0xc882b111a75c0c657fc507c04fbfcd2cc984f071 | *      | bnb | timing_signal   | qualquer tx às ~04:26 UTC = liquidação automática Gate.io — sinal de pressão venda
```

---

## ARQUITECTURA COMPLETA BSC PRÉ-LISTING (Jun 14) ⭐⭐⭐⭐⭐

> **Esta é a descoberta central de toda a investigação — para apresentar em Nansen/Arkham.**

```
CAMADA 1 — ORIGEM
  Rede Insider (20+ wallets) vendem tokens pré-listing
     ↓
CAMADA 2 — PRIME BROKER (clearinghouse bilateral OTC)
  0x0d0707963952f2fba59dd06f2b425ace40b492fe
     ↓ ramifica para 3 caminhos em paralelo
CAMADA 3A — ACCUMULATOR → SETTLEMENT
  0x055a3b37 (acumula todos os tokens)
     → 0xb7697d225fa (Exchange Settlement Hub — $2B net USDT, 1M txs, bilateral puro)
         → Binance Exchange

CAMADA 3B — MARKET MAKER 1
  0x218c18d0 (bilateral 24/7, 25+ tokens em simultâneo)
     → 0x238a358808 (= PANCAKESWAP VAULT [corrigido Jun 17] — DEX, NÃO Binance Treasury)
         → 0xb300000b ($1.04B USDT, 2.46M txs) ← reclassificar (prob. infra/LP PancakeSwap)
         → 0x286da956 ($545M USDT, 1.67M txs) ← reclassificar
         → 0x98445c3a ($541M USDT + 3.5B ARTX, 1.13M txs) ← reclassificar
         → 0x031942f2 ($369M USDT, 615k txs) ← reclassificar
         → ... 11 outros wallets (reclassificar — NÃO assumir Binance)

CAMADA 3C — MARKET MAKER 2 + OTC HUB
  0x4a4915a0 (market making SKYAI, LAB, SIREN, ZEST, MYX...)
     → 0x4e7ed91e (bot MM PancakeSwap, NÃO OKX [refutado Jun 17])
     → 0xce2213f4 (SKYAI 31.9M, USDT $11.8M)
     → 0xd5da17a8 (LAB, Beat, SIREN, TA, UB, ZEST, CYS...)
  0x3bc36786 (OTC hub multi-exchange, $706M USDT)
     → 0x238a358808 (= PancakeSwap Vault — mesmo destino DEX que 3B! [corrigido Jun 17])
     → 0xbc42145d (SKYAI dedicated, parou Mai 4)
     → 0x73d8bd54 (DEX/AMM pool — PancakeSwap?)
```

**❌ "Tudo converge para Binance" ESTAVA ERRADO (corrigido Jun 17).** O nó central `0x238a358808`
NÃO é Binance Treasury — é o **PancakeSwap Vault (DEX)**. A rede OTC LIQUIDA os tokens pré-listing
vendendo-os em liquidez DEX (PancakeSwap), não depositando na Binance. Reescrever a tese central:
é uma operação de **market making / liquidação on-chain via PancakeSwap**, não funil para a Binance.
Os wallets downstream ($1B+) precisam de reclassificação — não assumir que são infra Binance.

### Identidades confirmadas (Jun 14)

| Wallet | Identidade | Confiança |
|--------|-----------|-----------|
| `0x0d0707963952f2fba59dd06f2b425ace40b492fe` | Prime Broker OTC Clearinghouse | ⭐⭐⭐⭐⭐ |
| `0x055a3b37957bfbd3345bed9968e7e8dd56d67066` | Main Accumulator (router) | ⭐⭐⭐⭐⭐ |
| `0xb7697d225fa34bf1ebd3413adfa1c35b1be74729` | Exchange Settlement Hub ($2B USDT net) | ⭐⭐⭐⭐ Binance? |
| `0x238a358808379702088667322f80ac48bad5e6c4` | Binance BSC Treasury ($1B+ USDT distrib) | ⭐⭐⭐⭐ Binance |
| `0x218c18d02f0723291ce93aa5c0e5eb709903179a` | Market Making Engine 24/7 | ⭐⭐⭐⭐⭐ |
| `0x4a4915a02ebfd6e05132ff9f622646d157b719bb` | Second Market Maker | ⭐⭐⭐⭐⭐ |
| `0x3bc367866468d4f80096be899b66ab29d03f2717` | OTC Hub Multi-exchange | ⭐⭐⭐⭐⭐ |
| `0xc882b111a75c0c657fc507c04fbfcd2cc984f071` | Gate.io OTC Desk | ⭐⭐⭐⭐⭐ |
| `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` | DEX/AMM Hub (PancakeSwap?) | ⭐⭐⭐ |
| `0x4e7ed91e702ef2ff0c58e251c6e20d1dc1e31a5f` | Exchange HW downstream (OKX? Bybit?) | ⭐⭐⭐ |
| `0xb300000b72deaeb607a12d5f54773d1c19c7028d` | Binance BSC Vault (vanity addr, $1.04B) | ⭐⭐⭐⭐ |

### Supply concentration + dados de mercado (Jun 14 2026)

| Token | MC | FDV | Circ/Total | Vol/MC | Gate.io inventário | Gate.io % circ | Risco dump |
|-------|----|-----|-----------|--------|-------------------|---------------|------------|
| SIREN | ~$534M (antes crash) | — | — | 2.7x | 95M (vendeu) | — | ❌ CRASHOU -90% |
| HANA | $7.5M | $31.1M | 240M/1B (24%) | 0.13x | **70.7M** | **29.5% circ** | ⚠️ Gate.io news negativa |
| ESPORTS | $8.2M | $48.7M | 151.8M/900M (17%) | 1.8x | **31.7M** | **20.9% circ** | ✅ Team vesting, Gate.io big holder |
| VELVET | $145M | $344.7M | 420.8M/1B (42%) | 0.34x | **17.9M** | 4.3% circ | ❌ Exploit -52% + shorting; +111% recovery |
| TOWN | — | — | — | — | — | — | ⚠️ ~68% top 2 holders |

**HANA:**
- Top holder `0x483d66b5`: 411M = 41.1% total supply mas é vesting team (recebeu de single source)
- Gate.io tem **29.5% do supply circulante** em inventário OTC — vai listar
- Notícia negativa: "Binance Alpha Box Airdrop Changes" → airdrop rules mudaram, dump de holders airdrop
- Circulating muito baixo (24%) → possível diluição futura

**ESPORTS:**
- Top holder `0x49a0c23`: 240M = 26.7% total supply, é team allocation (4 txs de single source)
- Gate.io tem **20.9% do supply circulante** — sinal forte de listing iminente
- Só 16.9% do supply a circular → alto risco de diluição quando vesting desbloquear
- KuCoin já listou (Mai 2026), Binance Spot é próximo passo natural

**VELVET — "exploit" DESMASCARADO (Jun 14):**
- `0x6e0bad2c`: 471M > 420.8M circulante → é treasury/vesting (não circulante)
- **O crash de Jun 12 (-52%) NÃO foi exploit de protocolo — foi dump coordenado via prime broker**
- **Jun 12 16:00 UTC: 109 wallets venderam em simultâneo (~21.55M VELVET) ao broker**
  - Sellers incluem: `0x33ba873aa26b9c44c311e44bfd502dc7ad9cda8a` (SIREN seller), `0x8d17fbfb` (GAIN/SIREN core), `0xce0a9664` (insider 6/7 tokens)
  - Mesma rede insider que coordenou SIREN dump
- Recovery +111% pode ser short squeeze ou recompra coordenada pela mesma rede
- Shorting pesado antes do evento = insiders sabiam que o dump ia acontecer
- FDV $344M vs HANA/ESPORTS $30-48M — muito mais maduro
- Gate.io tem apenas 4.3% circ = Gate.io não coordenou este dump

**ESPORTS DUMP COORDENADO — MAI 25 2026 (Jun 15):**

Padrão idêntico ao VELVET Jun 12 — redistribuidor pré-posiciona antes do dump:
```
0x7ef905f806 (redistribuidor)
  Mai 20-21: distribui ESPORTS para 4+ wallets
    0x5e63d8fe: 19.8M → vendeu ao broker Mai 25 (1 tx)
    0xb7f68f5f: 19.9M → verificar destino
    0x96d5e410: 22.6M → provavelmente broker Mai 25
    0xa92a3f55: 2.4M
  Total estimado dump: ~46M ESPORTS
```
Diferença temporal: 4-5 dias entre pré-posicionamento e dump (VELVET: 6 dias).
Verificar: preço ESPORTS em Mai 25 2026?

---

**VELVET DUMP — ANÁLISE FORENSE COMPLETA (Jun 14 2026):**

Jun 12 16:39:39–16:43:56 UTC — **109 wallets em 4 minutos e 17 segundos**:

| Wallet | Já era | VELVET vendido |
|--------|--------|---------------|
| `0x96973f7b83a3c785d94e0a6d8712174abb81b748` | GAIN seller #6 / Insider 5/7 | **5.34M** (maior) |
| `0xc882b111a75c0c657fc507c04fbfcd2cc984f071` | Gate.io OTC Desk | 925k |
| `0xdd04f596569b09bb967ab9f20cdc1b7bc7495afd` | SIREN seller | 680k |
| `0x33ba873aa26b9c44c311e44bfd502dc7ad9cda8a` | SIREN seller | 360k |
| `0xb89baad6c41201ed1e2c564a9039309e8002631e` | SIREN seller | 173k |
| `0xe6451016f095835a0d5ef98a5c0092e47ddf0a93` | GAIN#5 / Insider 7/7 | 141k |
| `0x8d17fbfb03a6b7e8fdcfd60f1f9e6c08578ba5d7` | GAIN#2 / Insider 7/7 | 124k |
| `0x24a0d9928a3b6cd13a6210d0ff6d450a080fc266` | GAIN#4 / Insider 7/7 | 105k |
| `0xb85b098448b2aac4af96f5bdd9c6c02373a08975` | GAIN#3 / Insider 7/7 | 95k |
| `0x98f870ab30c0530b2e19d1adf5285200f52305a7` | Insider 6/7 | 66k |
| `0xd5da17a84314194e348649c89a65143a061f7190` | Exchange downstream (Entity 33) | 29k |
| `0xb2655ac91bb3536bcfa0993069da6affabadc33d` | Insider 6/7 | 6.4k |
| `0xce0a9664b28d28062fe59a03f34a5c855bc10570` | Insider 6/7 | 2.3k |
| `0xfb9bf2dde6dcdc44d3b89ddb477f8503a3b9d0bb` | Insider 6/7 | 1.8k |
| `0xea6d0eb93b28ea690c6d26820b392d4e4868338d` | "Meme trader" (reclassificar — é insider) | 5.2k |

**15 wallets da rede conhecida** participaram. Os restantes 94 são wallets novas que acumularam VELVET especificamente para este evento.

Padrão forense: vendas ordenadas do maior para o menor, executadas sequencialmente em 4 minutos. Isto é um **script automatizado com lista ordenada de wallets e montantes pré-calculados**. Não é "exploit de protocolo" — é coordenação OTC com o mesmo prime broker.

**CONCLUSÃO: VELVET = segundo caso de dump coordenado** (SIREN foi o primeiro). Gate.io participou (925k = 5% do inventário). O "exploit" é falso ou foi usado como trigger. **CFTC: 3 casos agora — SIREN, VELVET, e potencialmente futuros da mesma rede.**

---

## Estado actual — 14 Jun 2026

### O QUE FECHÁMOS (Jun 13-14)

| Item | Estado |
|------|--------|
| `0x055a3b37` outflows | ✅ Resolvido — destino dominante é `0xb7697d225fa...` |
| `0xb7697d225fa...` identidade | ✅ Exchange Settlement Hub — $2B net USDT, 1M txs, bilateral puro |
| OTC core wallet endereços | ✅ Corrigidos e confirmados via Dune |
| SIREN Gate.io upstream | ✅ Só o broker → Gate.io; último envio Mai 8 2026 |
| SIREN tese | ✅ Corrigida — era dump coordenado (82% supply) |
| Supply check HANA/ESPORTS | ✅ Sem concentração extrema; Gate.io tem 70.7M HANA + 31.7M ESPORTS em inventário |
| `0x238a358808` endereço completo | ✅ `0x238a358808379702088667322f80ac48bad5e6c4` confirmado |
| Cross-reference wallets | ✅ Rede insider de 20+ wallets identificada (ver secção abaixo) |
| Supabase | ✅ 15 infra wallets + 12 token wallets inseridos |
| 1.txt | ✅ Entity 25-34 documentados (Jun 14) |
| Metodologia | ✅ Modelo corrigido — broker detecta eventos, não direcção |
| `0x218c18d0` outflows | ✅ Envia para `0x238a358808` (Binance Treasury) em 11 tokens |
| `0x238a358808` identidade | ✅ Binance BSC Treasury — distribui $1B+ para 15+ wallets Binance infra |
| `0x4a4915a02` outflows | ✅ Vai para 3 exchange wallets downstream (`0x4e7ed91e`, `0xce2213f4`, `0xd5da17a8`) |
| HANA/ESPORTS supply source | ✅ Team allocation (vesting) — não é insider dump |

| VELVET "exploit" Jun 12 | ✅ Confirmado dump coordenado via broker — 109 wallets em simultâneo às 16:00 UTC |

### 🔲 PENDENTE (menor prioridade, para após entrevistas)

| Tarefa | Porquê |
|--------|--------|
| `0x4e7ed91e7` confirmar identidade | OKX ou Bybit? $40.8M USDT + SKYAI sugere exchange major |
| `0xb300000b72` confirmar identidade | Binance vault? Vanity addr "b300000" — investigar outflows |
| VELVET: quantificar dump | ✅ ~15M vendidos via broker em 4min17s |
| VELVET: 109 sellers identificados | ✅ 15 da rede conhecida + 94 via distribuidor `0x150c8a` |
| VELVET: cadeia origem confirmada | ✅ Project Treasury `0x579d36cc` → VC `0x6bff1c3e` → dump 11 meses depois |
| `0x39927a70` identificado | ✅ Veterano multi-token: SIREN activo Jun 13, VELVET Jun 12, BLESS Jun 5 |
| `0x1f7e66db` identificado | ✅ HANA 24M + VELVET + SKYAI 5.4M — bilateral $15M USDT; novo nó central |

### VELVET VC MAP — estado de cada alocação

| Wallet | Tokens | Estado Jun 14 |
|--------|--------|--------------|
| `0xd19dce53` | 759M (team) | Enviou 645M → `0xcf990fa3` (vesting contract) — equipa a receber progressivamente |
| `0x6bff1c3e` | 72.7M (VC #1) | ✅ DUMPADO Jun 12 via `0x150c8a` → 109 wallets |
| `0xa3277d68` | 50M (VC #2) | Distribuindo progressivamente desde Jul 2025 — pequenos airdrops/staking. 28.2M movidos Mar 4 → `0x80952ba0` que distribui a sub-wallets. Não via broker. |
| `0xcd57107c` | 35M (VC #3) | Enviou 35M → `0xe2e8fa23` em Mar 4. **`0xe2e8fa23` ainda tem os 35M — dump futuro pendente!** |
| `0x029d7bd5` | 32M (VC #4) | Enviou 32M → `0x93deb693` em Jul 2025 — não rastreado além disso |

**ALERTA:** `0xe2e8fa23` tem 35M VELVET parados desde Mar 4 — segunda onda de dump provável.

### ✅ PENDENTES RESOLVIDOS Jun 17

| Tarefa | Estado |
|--------|--------|
| `0x93deb693` — VC #4 destination (32M, Jul 2025) | ✅ Zero Arkham (só tokens). Monitorizar se VELVET listar. |
| `0xcf990fa3` — team vesting contract (645M) | ✅ Zero Arkham (contrato vesting). Monitorizar desbloqueios. |
| `0x4e7ed91e7` identidade OKX vs Bybit | ✅ Bot MM PancakeSwap (confirmado Arkham UI Jun 17). Não é OKX nem Bybit. |
| `0xe97b1f05` SIREN+VELVET sem label | ✅ Trader multi-exchange base Bitget. Amplitude de portfólio, não insider. |
| `0x218c18d0` 20+ tokens sem label | ✅ Gate.io operator BSC. Sem ligação a insiders. |
| `0xb7697d225fa` counterparty MEV bot | ✅ MEV Bot profit wallet (treasury de saída do bot). |

### 🔲 PENDENTE — ALERTA ACTIVA

| Tarefa | Nota |
|--------|------|
| `0xe2e8fa23` — 35M VELVET VC#3 PARADOS | ⚠️ DUMP PENDENTE — verificado Jun 17, ainda zero saídas |
| `0xae8633d1` — 5M VELVET Jun 5 | Baixa prioridade — DEX sell provável |
| SIREN + VELVET dossier CFTC | Decisão do utilizador — 3 casos documentados |

### ✅ WALLETS — TODAS AS PRINCIPAIS INVESTIGADAS

| Wallet | Estado | Identidade |
|--------|--------|------------|
| `0x0d0707963952f2fba59dd06f2b425ace40b492fe` | ✅ COMPLETO | Prime Broker OTC Clearinghouse |
| `0x055a3b37957bfbd3345bed9968e7e8dd56d67066` | ✅ COMPLETO | Main Accumulator → Settlement Hub |
| `0xb7697d225fa34bf1ebd3413adfa1c35b1be74729` | ✅ COMPLETO | Exchange Settlement Hub ($2B USDT) |
| `0x238a358808379702088667322f80ac48bad5e6c4` | ✅ COMPLETO | Binance BSC Treasury |
| `0x218c18d02f0723291ce93aa5c0e5eb709903179a` | ✅ COMPLETO | Market Making Engine → Binance Treasury |
| `0x3bc367866468d4f80096be899b66ab29d03f2717` | ✅ COMPLETO | OTC Hub → Binance Treasury |
| `0x4a4915a02ebfd6e05132ff9f622646d157b719bb` | ✅ COMPLETO | Second Market Maker → 3 exchange HWs |
| `0xc882b111a75c0c657fc507c04fbfcd2cc984f071` | ✅ COMPLETO | Gate.io OTC Desk |
| `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` | ✅ COMPLETO | DEX/AMM Pool (PancakeSwap-like) |
| `0xb300000b72deaeb607a12d5f54773d1c19c7028d` | ⚠️ PARCIAL | Provável Binance Vault (outflows não investigados) |
| `0x4e7ed91e702ef2ff0c58e251c6e20d1dc1e31a5f` | ⚠️ PARCIAL | Exchange HW downstream (OKX? Bybit?) |

---

### ⚡ DESCOBERTAS PRINCIPAIS desta sessão (Jun 15 — manhã / nova sessão)

1. **BROKER RE-SCAN Jun 14-15: 5 novos dumps coordenados** (todos com txs=senders em janela de minutos)
   - GAFI: 169 wallets, Jun 14 06:09-06:14 UTC (5 min)
   - CARAT: 166 wallets, Jun 14 16:46-16:51 UTC (5 min)
   - AI: 142 wallets, Jun 14 17:41-17:45 UTC (4 min)
   - Beat: 133 wallets, **Jun 15 00:25:58-00:26:29 UTC (31 segundos)** ← hoje de manhã
   - ZEST: 89 wallets, Jun 14 19:48-19:50 UTC (2.5 min)
   - SDM: 5 senders, 31.7M tokens, Jun 15 (menor)

2. **HANA — 4.º dump coordenado confirmado em Jun 4 2026:**
   - 99 wallets venderam ao broker entre 15:53:07 e 15:54:38 UTC (91 segundos!)
   - Padrão idêntico ao VELVET (109 wallets, 4min17s)
   - Top sellers no evento: `0xd5da17a8` (32.4M), `0xe92bd58a` (15.6M), `0xc527f051` (11.9M)
   - 12+ wallets conhecidas da rede participaram (cross-token veterans)
   - Broker ainda activo pós-dump: enviou para Gate.io em Jun 5 04:26 UTC

3. **HANA broker full flow mapeado:**
   - Gate.io recebeu **245.9M HANA** do broker (6 txs, Set 28 2025 → Jun 5 2026)
   - Gate.io devolveu **175.2M** ao broker — net: Gate.io tem 70.7M acumulado
   - `0xe97b1f05` (strategic holder) recebeu **158.9M HANA** do broker (1857 txs até Abr 2026)
   - `0x055a3b37` (accumulator) recebeu 157.6M (5228 txs)
   - `0xe5b1191810fd39c2a4544bc4b9319a4e23dfc037` — novo wallet: recebeu 129.7M em 4 txs Out 11

4. **HANA supply chain confirmada:**
   - Mint: Mai 29 2025, 1B tokens → deployer `0x3f241b9db8`
   - Deployer → distribuidor `0xfd30179319574f1e2511ae0ed4df9b5558a4654e` (1 tx Mai 30)
   - Distribuidor → alocações VC/parceiros Sep 2025:
     - `0xe3deef2f` → 140.3M (Sep 23, depois → `0xf287a07e5c`)
     - `0x4b56e565` → 90M (Sep 25-26, depois → `0xf104155a` 75M)
     - `0x097bebc0` → 59.9M (Sep 19-26)
     - `0x5d1389b4` → 56M (Sep 23-26)

5. **`0x06bdbdc` (80M HANA) = alocação equipa, não insider:**
   - 50M do treasury `0x483d66b5` em Mar 17 2026
   - 30M de `0x7780846d` em Abr 1 2026
   - Zero outflows — equipa a segurar

6. **`0x7dd17204b864d1a3599b8b206b5d985b46c761ef` — novo destino activo:**
   - Recebeu 34.5M HANA do broker, **último: Jun 9 2026** (muito recente)
   - Também aparece no scan geral como destino HANA do broker em Mai 27 2026

### ⚡ DESCOBERTAS PRINCIPAIS desta sessão (Jun 16 — madrugada)

1. **`0x7dd17204` — NÃO é 6º membro da rede core 7/7.** Verificado como sender E receiver: só toca VELVET, HANA, LAB, GAIN (de forma circular — recebe e envia os mesmos 4). Não toca QAIT, TOWN, XTER, DARK, SKYAI. SIREN (9.79) e ESPORTS (4 unidades, 1 tx) são dust/spam, não posições reais. **Conclusão: wallet intermediário do cluster VELVET-HANA-LAB-GAIN, separado da rede dos 4 insiders core confirmados (`0x24a0d992`, `0xb85b0984`, `0x8d17fbfb`, `0xe6451016`). Hipótese do 6º membro REFUTADA.**
2. **Gate.io VELVET 04:26 UTC — sem novo tranche em Jun 16.** Verificado às ~04:30 UTC: último tranche continua a ser Jun 15 04:26:41 UTC (2,745,291.82 VELVET). Pode ter saltado o dia ou esgotado o lote previsto para este ritmo. Manter observação.

### ⚡ DESCOBERTAS PRINCIPAIS desta sessão (Jun 15 — noite)

1. **VELVET Gate.io liquidação em curso — CONFIRMADA HOJE:**
   - Jun 12 16:42 UTC: Gate.io vendeu **925k VELVET** ao broker (durante o dump coordenado)
   - **Jun 15 04:26:41 UTC (HOJE):** Gate.io vendeu **2.745M VELVET** ao broker (assinatura 04:26 Gate.io)
   - Total liquidado: **~3.67M** de 17.9M (~20% da posição)
   - Restante estimado: **~14.23M VELVET** ainda em Gate.io
   - Gate.io está a liquidar em tranches — próxima tranche esperada em dias

2. **Broker a redistribuir VELVET ao longo de Jun 15 — wallets a acumular para próximo dump:**
   - `0x4e7218ee69950f4822c7d7d981935e900ad00a39` — maior receptor: ~210k VELVET (múltiplas txs)
   - `0x03631c388fb01e0d929627b614eeb501c0ef9dce` — ~50.6k VELVET (1 tx)
   - `0xe48ebd633200108085ab7413d38af7ac894bcb65` — ~38.7k VELVET (3 txs)
   - `0xc9dfb45265ba3e312d4fbb7ee6effafcc85ddad3` — ~14.1k VELVET
   - `0x7dd17204b864d1a3599b8b206b5d985b46c761ef` — ~13k VELVET (também recebe HANA)
   - Dezenas de outros wallets recebem quantidades pequenas via `0x055a3b37`
   - **Pattern: broker a pré-posicionar wallets com VELVET — próximo dump a preparar**

3. **`0x4e7218ee` — novo wallet prioritário para seguimento:**
   - Maior receptor VELVET do broker hoje (210k em múltiplas txs entre 00:48 e 14:23 UTC)
   - Ainda não investigado — pode ser exchange HW ou insider premium
   - Nota: diferente de `0x4e7ed91e` (OKX candidate do Entity 33)

4. **Broker a recrutar wallets hoje (BNB gas):**
   - 30 wallets receberam BNB gas (0.001-0.046 BNB) entre 15:41-20:08 UTC Jun 15
   - Rede a expandir activamente — próximos dumps com wallets novas

5. **`0x53f78a071d` — redistribuidor cross-token confirmado (SIREN+Beat+GAFI+LAB+ASTER):**
   - Distribui SIREN para 377 wallets (244M SIREN total)
   - Distribui Beat para 6 dump wallets (186k Beat)
   - Recebe SIREN de 10 wallets feeders ainda activas em Jun 13 2026:
     - `0x8dac80ce`: 47.9M SIREN (activo Jun 8 2026)
     - `0x9021069c`: 36M SIREN (2,549 txs — activo Jun 13!)
     - `0xb8e6d31e`: 35M SIREN (activo Jun 9)
     - `0x39ac22b2`: 29.8M SIREN (activo Jun 13)
     - `0x9f2fa854`: 24.7M SIREN (activo Jun 13)
     - `0xac474892`: 20M SIREN (activo Jun 13)
     - + 4 outros feeders
   - **SIREN ainda a entrar no sistema em Jun 13 — rede OPERACIONAL**

6. **`0x4982085c9e` — duplo papel confirmado:**
   - Move $36M+ FDUSD para Binance (market maker legítimo)
   - E em simultâneo distribui Beat para 5 dump wallets (305k Beat)
   - Recebe supply de `0x7dd17204` (broker outlet) antes de redistribuir

### ⚡ DESCOBERTAS PRINCIPAIS desta sessão (Jun 15 — tarde)

1. **ESPORTS — dump coordenado confirmado Mai 25 2026** — `0x7ef905f806` pré-posicionou 4+ wallets com ESPORTS (Mai 20-21) → ~46M vendidos ao broker em Mai 25. Padrão idêntico ao VELVET Jun 12. Verificar preço ESPORTS nessa data.
2. **`0xea6d0eb9` — BSC veteran aggregator, 100+ tokens desde Jun 2024** — NÃO é project insider clássico. É um agregador profissional que recebe memecoins via reward distributors (BabyElon 4Q, BabyNeiro 3.3Q, CAT 70T...) e liquida tudo ao broker sistematicamente. Activo 18+ meses. A Set 26 2024 expandiu abruptamente para 30+ tokens novos num único dia. Binance Alpha tokens (TOWN, GAIN) são uma fracção do portfólio geral. Útil como "antena" do broker — qualquer token novo que aparecer neste wallet vai ao broker.
3. **SIREN cluster Feb 2025 — origem: BSC infraestrutura** — `0x5c952063` não é insider, é protocolo BSC com 72M+ txs BNB. O projecto SIREN usou esta infra para distribuir tokens a investidores em Feb 8 2025 (14 dias antes dos sellers venderem ao broker).
4. **`0xe92bd58a` — 30 tokens, DKS 454M** — multi-token insider desde Feb 2025, ainda activo Jun 4 2026.
5. **`0x744727a6` — veterano desde Jan 1 2025** — começou com memecoins em escala maciça (BabyDoge 279T, WHY 17T, Cheems 5.4T) e evoluiu para HANA (96.6M), Q (119M), COAI, STBL, Beat, ASTER... 40+ tokens.
6. **Cross-reference SIREN+HANA+ESPORTS completo** — 2 novos wallets em 3 tokens: `0x6cdf9452` e `0x33ba873a` (ver Entity 39). Jun 3 2026: três wallets liquidaram SIREN e ESPORTS no mesmo dia.

---

### ⚡ DESCOBERTAS PRINCIPAIS desta sessão (Jun 13)

1. **SIREN ❌ CRASH -90%** — tese de pré-listing errada. Ver secção SIREN revisada abaixo.
2. **CICLO FECHADO** — cadeia completa descoberta: Sellers → Broker `0x0d0707` → Accumulator `0x055a3b37` → **`0xb7697d225fa34bf1ebd3413adfa1c35b1be74729`** (Exchange Settlement Hub, $2B net USDT, 1M txs)
3. **`0x218c18d0` NÃO é meme bot** — é um market making engine de alta frequência que opera QAIT, SIREN, BTW e 20+ tokens em simultâneo.
4. **Endereços completos dos OTC core sellers confirmados** — `0x016b7836` é o maior com 125.9M GAIN. 7 sellers SIREN activos em Jun 13. Ver Entity 26 em 1.txt.
5. **GAIN = vesting unlock semanal**, não pré-listing. Bursts a cada ~7 dias (Jun 2, 6, 13), distribui diariamente entre bursts.
6. **XTER e TOWN** — ambos em Binance Alpha, sem Binance Spot, apareceram hoje no broker com 15-21 sellers simultâneos.
7. **`0x0668b4d2`** — novo satellite OTC encontrado (recebe XTER, D, PARTI do broker e redistribui).

---

---

## REDE INSIDER — CROSS-REFERENCE 7 TOKENS (Jun 14) ⭐⭐⭐⭐⭐

> **Esta é a descoberta mais valiosa para Nansen/Arkham.**
> Os mesmos wallets vendem múltiplos tokens pré-listing Binance Alpha ao broker — são insiders com acesso simultâneo a vários projectos.

### Wallets com acesso a TODOS OS 7 tokens (HANA, VELVET, ESPORTS, TOWN, XTER, WARD, SIREN):

| Wallet | Tokens | Txs | Já identificado? |
|--------|--------|-----|-----------------|
| `0x24a0d9928a3b6cd13a6210d0ff6d450a080fc266` | **7/7** | 128 | ✅ OTC core seller (35.8M GAIN) |
| `0xb85b098448b2aac4af96f5bdd9c6c02373a08975` | **7/7** | 128 | ✅ OTC core seller (44.7M GAIN) |
| `0x8d17fbfb03a6b7e8fdcfd60f1f9e6c08578ba5d7` | **7/7** | 117 | ✅ OTC core seller (47.8M GAIN) |
| `0xe6451016f095835a0d5ef98a5c0092e47ddf0a93` | **7/7** | 116 | ✅ OTC core seller (31.8M GAIN, parou Mai 4) |
| `0xea6d0eb93b28ea690c6d26820b392d4e4868338d` | **7/7** | 32 | ❌ NÃO é insider core — ver nota Jun 16 abaixo |

> **CORRECÇÃO Jun 16 2026 — `0xea6d0eb9` NÃO faz parte da rede core sincronizada:**
> - VELVET Jun 12: vendeu 66s DEPOIS dos 4 insiders core (16:42:27 vs janela 16:41:01-16:41:21), com 20-30x menos volume (5.2k vs 95-140k)
> - HANA Jun 4: nem aparece na janela do dump coordenado (15:53:39-43 UTC). As 9 vendas HANA dele estão espalhadas Set 2025→Jan 2026, sempre ~10:00-12:00 UTC (horário de rotina)
> - **Conclusão: é um agregador profissional independente (100+ tokens, "antena" do broker), não está sincronizado com o script automatizado dos 4 insiders core. Toca nos mesmos 7 tokens por amplitude de portfólio, não por acesso privilegiado coordenado.**

### Wallets com acesso a 6/7 tokens:

| Wallet | Tokens | Txs |
|--------|--------|-----|
| `0xfb9bf2dde6dcdc44d3b89ddb477f8503a3b9d0bb` | SIREN/VELVET/XTER/TOWN/WARD/HANA | 69 |
| `0x89e94acc3a619fbea6aa28c26eec8b6f01e2ac8b` | WARD/HANA/SIREN/TOWN/VELVET/ESPORTS | 49 |
| `0xb2655ac91bb3536bcfa0993069da6affabadc33d` | SIREN/VELVET/HANA/XTER/TOWN/WARD | 31 |
| `0x98f870ab30c0530b2e19d1adf5285200f52305a7` | WARD/TOWN/XTER/VELVET/HANA/ESPORTS | 27 | ✅ (GAIN seller #7) |
| `0xce0a9664b28d28062fe59a03f34a5c855bc10570` | XTER/TOWN/WARD/SIREN/VELVET/HANA | 23 |

### Wallets com acesso a 5/7 tokens (seleção):
`0x96973f7b` (5t, 74tx), `0xd0be1fde` (5t, 21tx), `0xd2ffbca3` (5t, 19tx), `0x15807bf2` (5t, 16tx), `0x4b32dcfb` (5t, 16tx), `0x4306d7db` (5t, 15tx), `0x423c757b` (5t, 12tx)

### Interpretação:
- Os 4 wallets OTC core (que vendem GAIN) também vendem TODOS os outros tokens pré-listing
- São a **infraestrutura OTC central** de toda a rede Binance Alpha BSC
- Têm acesso a tokens de projectos diferentes antes de qualquer listing público
- `0xea6d0eb9` é novo — 7/7 tokens, 32 txs — investigar identidade
- **Para Nansen/Arkham**: estes wallets são o melhor ponto de entry para rastrear o fluxo pré-listing em BSC

### Wallets confirmados em 3 tokens (SIREN+HANA+ESPORTS) — para além dos 7/7 (Jun 15):

| Wallet | SIREN | HANA | ESPORTS | Nota |
|--------|-------|------|---------|------|
| `0x6cdf94520d00ef13b9b56f3815107b9529b8957b` | 19.7M (Mar 21 2025) | 96.9M (Set 2025) | 7.8M (Jul 2025) | Entrada mais antiga no SIREN |
| `0x33ba873aa26b9c44c311e44bfd502dc7ad9cda8a` | 30.2M (Mai 31 2025) | 45.7M (Out 2025) | 5.7M (Ago 2025) | Alta actividade em todos |
| `0xdd04f596569b09bb967ab9f20cdc1b7bc7495afd` | 36.1M (Mar 30 2025) | 40M (Out 2025) | — | 2/3 confirmado, 70+ txs SIREN |
| `0xbc0be9e090224983eb9bff63eb9504dd55994e17` | — | 59.7M | 2.5M | HANA posição grande |
| `0x9e4a7a68e6b94f852f60f5eaf1c505e37d2e7d35` | 9M | — | 1.85M | Jun 3 2026: vendeu ambos no mesmo dia |
| `0x41cd20a8871176893090fcf29412e6d9fbcffe20` | 6.4M | — | 1.73M | Jun 3 2026: vendeu ambos no mesmo dia |
| `0x2004b06ea7c2f5eec504ec8489ec210dfe220fd5` | 5.9M | — | 1.59M | Jun 3 2026: vendeu ambos no mesmo dia |

**Nota Jun 3 2026:** três wallets venderam SIREN + ESPORTS no mesmo dia = liquidação coordenada cross-token.

---

## SUPPLY CONCENTRATION — HANA, ESPORTS (Jun 14)

### HANA — top holders on-chain:
| Holder | Net Balance | Nota |
|--------|-------------|------|
| `0x483d66b57c64b6b4c80a0b37932814d1d6edcd25` | **411M** | MAIOR HOLDER — possível team/vesting |
| `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` | 260M | Exchange (1.7B in/1.44B out = bilateral) |
| `0x06bdbdcaa165b8ddce5384fbad4b0365cbad8d9e` | 80M | Pure holder, zero outflows |
| **`0xc882b111` (Gate.io OTC)** | **70.7M** | Gate.io tem inventário HANA — **listing Gate.io iminente ou em curso** |

**Concentração HANA:** não há um único holder com >50% do supply visível — distribuição mais saudável que SIREN.
**Sinal:** Gate.io com 70.7M = Gate.io está preparada para listing. HANA pode listar Gate.io primeiro (como SIREN fez).

### ESPORTS — top holders on-chain:
| Holder | Net Balance | Nota |
|--------|-------------|------|
| `0x49a0c2366936b115d6877438175ee4b97d6dab7c` | **240M** | Top holder ESPORTS |
| `0x99d4b3f50b14bfc67892c472f4053ee3483d87b9` | 212M | Segundo maior |
| `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` | 128M | Exchange (397M in/268M out = bilateral) |
| **`0xc882b111` (Gate.io OTC)** | **31.7M** | Gate.io também tem ESPORTS — **confirmado** |
| `0xbcc2b85419ab2fcee8042af8e9ee9e1643d4adcb` | 35M | Holder estático |

**Concentração ESPORTS:** 240M + 212M nos dois maiores holders — investigar se são team/vesting.
**Sinal Gate.io:** `0xc882b111` tem 31.7M net ESPORTS — Gate.io como próximo listing (KuCoin Mai 22 foi o primeiro).

### VELVET — top holders on-chain:
| Holder | Net Balance | Nota |
|--------|-------------|------|
| `0x6e0bad2c077d699841f1929b45bfb93fafbed395` | **471M** | MAIOR HOLDER (645M in, 173M out) |
| `0x75e7488ac067f07948739bfb550213b47db094bb` | 160M | Pure holder (zero outflows) |
| `0xd19dce537125dfb5e76d7131668c4d5e4172b56c` | 107M | Bilateral (759M in/652M out = exchange) |
| `0xe2e8fa23dda79231e4bd237321fd843fd7e9e0a7` | 35M | Static holder (zero outflows) |
| **`0xc882b111` (Gate.io OTC)** | **17.9M** | Gate.io tem inventário VELVET |

### TOWN — top holders on-chain:
| Holder | Net Balance | Nota |
|--------|-------------|------|
| `0x2064e723bbf590bfe3f4b72c91a570ad469cb5af` | **380M** | ~38% supply ← ALTO |
| `0x6a3b5276c23dbf1834c8d06433b312e408b1f9f6` | 300M | ~30%, zero outflows = provavelmente team/lock |
| `0xdb435a0cca19df36a82e2fd19fe0ee58d71c7a03` | 170M | ~17% |
| `0x73d8bd54` (DEX/AMM) | 170M | Bilateral 6.98B in/6.81B out = pool |
| `0x48d9cf74639d9a70ed9144f42e6f260a0b5e6df3` | 130M | Holder estático |

**⚠️ TOWN concentração:** Top 2 holders = **680M de ~1B supply = 68%** → risco de dump moderado-alto. Aplicar filtro de metodologia: verificar destino tokens no broker antes de classificar.
**TOWN diferença de SIREN:** `0x6a3b5276` (300M) tem zero outflows — pode ser vesting locked da team, não dump eminente.

### `0x73d8bd54f7cf5fab43fe4ef40a62d390644946db` — DEX/AMM HUB (PancakeSwap?) [INVESTIGADO Jun 14]
- Portfolio: SIREN (890,818 txs!), RAVE (531k), BULLA (492k), RIVER (466k), 我踏马来了 (345k meme chinês), FIGHT (245k), GWEI, memes...
- Manuseia meme tokens + pre-listing em simultâneo = **NÃO é exchange OTC, é DEX/AMM pool**
- NET positions: SIREN +193M, TOWN +170M, FIGHT +337M, BULLA +397M — pode ser PancakeSwap LP
- WARD entrou em 4 Fev 2026 (mesmo dia do Binance Alpha listing) = LP seeds na data de listing
- **Conclusão: PancakeSwap pool ou BSC DEX aggregator — não é insider, é infra de mercado**

---

## GATE.IO INVENTORY SIGNAL — Próximos Listings Gate.io (Jun 14) ⭐⭐⭐⭐⭐

> **`0xc882b111` (Gate.io OTC Desk) acumula inventário antes de listar um token.**
> Confirmado com SIREN: Gate.io acumulou 95M SIREN → listou. Agora tem stock em 3 outros tokens.

| Token | Gate.io Net Holdings | Sinal |
|-------|---------------------|-------|
| SIREN | ~~95M~~ (já listado, distribuído) | ✅ Confirmado — padrão funciona |
| **HANA** | **70.7M net** (245M in, 175M out) | 🔴 Listing Gate.io IMINENTE |
| **ESPORTS** | **31.7M net** (55M in, 23M out) | 🔴 Listing Gate.io IMINENTE |
| **VELVET** | **17.9M net** (42M in, 24M out) | 🟡 Em preparação |

**Interpretação:** Gate.io compra inventário via broker OTC antes de anunciar o listing.
Quando o inventário está acumulado (e os outflows ainda são pequenos), o listing é iminente.
HANA com 70.7M é o mais avançado — pode listar Gate.io nos próximos dias/semanas.

---

## SCAN BROKER JUNHO 2026 — 88 tokens com 5+ senders (Jun 13)

### RANKING POR SENDERS (só candidatos relevantes):

| Token | Senders | Txs | Net In | Status | Prioridade |
|-------|---------|-----|--------|--------|------------|
| **SIREN** | **198** | 4,800 | +17.7M | Binance Futures+Alpha ✓, Spot NÃO | ⭐⭐⭐⭐⭐ #1 |
| **ESPORTS** | **146** | 264 | bilateral | Binance Alpha Jul25, KuCoin Mai26, sem Spot | ⭐⭐⭐ |
| PIEVERSE | 146 | 330 | bilateral | desconhecido | ⭐ investigar |
| SAHARA | 135 | 869 | bilateral | JÁ NA BINANCE (crash -56% Jun 9, unlock Jun 26) | ❌ pós-listing |
| GMRX | 144 | 162 | +2.64B parou Jun 5 | Binance listed, $746k MC | ❌ micro-cap |
| NBT (NanoByte) | 143 | 151 | +10.6M | DEX only, $0.0016, ignorar | ❌ micro-cap DEX |
| COAI | 134 | 643 | bilateral | desconhecido | ⭐ |
| NETX | 132 | 248 | +400k | desconhecido | ⭐ |
| D | 129 | 419 | +2.9M | desconhecido | ⭐ |
| **HANA** | **97** | 165 | **burst 89.5M Jun4** | **Binance Alpha Set 2025, sem Spot** | ⭐⭐⭐⭐ |
| **VELVET** | **94** | 1,825 | bilateral | **Binance Alpha Feb26 (2º airdrop), sem Spot** | ⭐⭐⭐⭐ |
| BEAM (≠BEAMX) | 89 | 98 | +25.1M parou Jun11 | Token diferente, investigar | ⭐⭐ |
| **TOWN** | 79 | 899 | **+55M** | Binance Alpha Ago 2025, sem Spot | ⭐⭐⭐ |
| CROSS | 77 | 259 | +1.3M | desconhecido | ⭐ |
| DEGOV2 | 75 | 116 | bilateral | desconhecido | ⭐ |
| **PRAI** | **71** | 77 | **+31M** | Privasea AI — Bitget/KuCoin, sem Binance | ⭐⭐⭐ |
| **OLE** | **69** | 71 | **+3.5M (97% hold)** | OpenLeverage, DEX only, burst Jun 7-10 | ⭐⭐ |

### ⭐⭐⭐⭐ HANA (Hana Network) — candidato forte Jun 13
- Contract BSC: `0x6261963ebe9ff014aad10ecc3b0238d4d04e8353`
- **Binance Alpha: 26 Set 2025** — 9 meses sem Spot listing
- HTX listing: Janeiro 2026 (pump 157%)
- Broker activo desde Jan 1 2026 (151 dias de dados):
  - Jan 16: 22M in, 12 senders (provável coincide com HTX listing)
  - Mai 21-Jun 3: SÓ OUTFLOWS (broker a distribuir acumulação anterior)
  - **Jun 4: 89.5M in, 99 wallets em 91 segundos** ← dump coordenado confirmado
  - Jun 5: redistribuição imediata → Gate.io 04:26 UTC
  - Jun 6-13: pequenos outflows contínuos
- **Jun 4 = 4.º dump coordenado confirmado** (ver Entity 43)
- Tese: HANA aguarda Binance Spot; Gate.io tem 70.7M de inventário acumulado

### ⭐⭐⭐⭐ VELVET (Velvet Capital DeFAI) — candidato forte Jun 13
- Contract BSC: `0x8b194370825e37b33373e74a41009161808c1488`
- **Binance Alpha: Fevereiro 2026 (SEGUNDO airdrop)** — sem Binance Spot ainda
- Listings actuais: Gate.io ✓, KuCoin ✓, Bitget ✓, MEXC ✓, BingX ✓, Kraken ✓
- Broker activo desde Jan 1 2026, **1,825 txs em Junho, 94 senders, activo Jun 13** ✅
- Destinos: `0x055a3b37` (1,387 txs), `0x3bc367866` (158 txs), `0x218c18d0` (39 txs)
- `0xe97b1f05` (strategic holder) acumulou VELVET Jan 1-20 e PAROU (igual ao padrão SIREN!)
- Tese: segundo airdrop Alpha Feb 2026 = preparação para Spot; acumulação estratégica em Jan

### ⭐⭐⭐ ESPORTS (Yooldo Games) — Binance Alpha → KuCoin → Binance Spot?
- Contract BSC: `0xf39e4b21c84e737df08e2c3b32541d856f508e48`
- **Binance Alpha: 19 Jul 2025** — airdrop 900 tokens para 160+ Alpha Points
- KuCoin: **22 Mai 2026** (token a $0.7168 antes do listing)
- Binance Spot: NÃO ainda
- Broker activo desde Jan 4 2026; **146 senders em Junho**
- `0x3bc367866` parou de receber ESPORTS em **25 Mai** (3 dias após KuCoin listing) ← marker temporal
- Destinos actuais: `0x055a3b37` (até Jun 9), `0x18a3a7fb...` (novo, activo Jun 12)
- Tese: Binance Alpha Jul 2025 → KuCoin Mai 2026 → Binance Spot próximo?

### ⭐⭐⭐ PRAI (Privasea AI) — candidato Jun 13
- Contract BSC: `0x899357e54c2c4b014ea50a9a7bf140ba6df2ec73`
- Listings actuais: Bitget (Mai 2025), KuCoin, MEXC — **NÃO Binance**
- Broker Jun 2-12: 77 txs, **71 senders, 34M in / 3M out = +31M net**
- Parou Jun 12 — ciclo pode ter fechado
- Tese: Bitget/KuCoin first → Binance candidato

### ⭐⭐ OLE (OpenLeverage Token V2) — fresco Jun 7-10
- Contract BSC: `0xb7e2713cf55cf4b469b5a8421ae6fc0ed18f1467`
- DEX only, 1,787 holders, price ~$0.0077
- Broker Jun 7-10: 71 txs, **69 senders, 3.6M in / 67k out** (97% acumulado)
- Parou Jun 10 — 3 dias de actividade intensa, depois silêncio
- Tese: pré-listing CEX iminente após acumulação concentrada

---

### ⭐⭐⭐⭐ XTER (Xterio) — candidato pré-listing Binance spot FORTE
- Contract BSC: `0x103071da56e7cd95b415320760d6a0ddc4da1ca5`
- **Binance Alpha: 19 Mai 2025** (airdrop, 194 pontos mínimos) → pré-cursor clássico de spot listing
- **SEM listing Binance spot ainda** (Jun 2026)
- Exchanges actuais: Bitget (Jan 2025), Kraken (Ago 2025), LBank (Jul 2025), Bithumb, Bybit
- Preço actual: ~$0.018
- **Broker activity Jun 12 2026:**
  - 00:04 UTC: broker envia 17k XTER para `0x218c18d0`
  - **17:17-17:18 UTC: 15 sellers simultâneos → broker** (580k, 106k, 61k, 55k, 53k, 51k... 3.7M total)
  - 17:20, 17:36, 17:55 UTC: broker redistribui para `0x0668b4d2` (satellite OTC, ver abaixo)
  - Jun 13 01:48: última tx registada (total 3.76M tokens, 30 senders distintos)
- **Padrão**: idêntico a GENIUS/HYPER/SIGN — multi-seller coordenado → broker → redistribuição OTC
- **Estimativa listing Binance spot**: semanas/meses (seguindo Binance Alpha → spot que levou TOWN/XTER)

### ⭐⭐⭐ TOWN (Alt.town) — candidato pré-listing Binance spot
- Contract BSC: `0x1aaeb7d6436fda7cdac7b87ab8022e97586d2da1`
- **Binance Alpha: 26 Ago 2025** → Binance Alpha 2.0 abriu 27 Nov 2025
- **SEM listing Binance spot ainda** (Jun 2026)
- Market cap actual: ~$5.88M (muito pequeno — alto upside potencial no listing)
- **Broker activity Jun 13 2026:**
  - **01:59-02:01 UTC: 21 sellers simultâneos → broker** (77.7M tokens total)
- Fundadores: ex-CTO SM Entertainment + equipa Web3; integração Binance Wallet completa
- **Estimativa listing Binance spot**: weeks (padrão Alpha → spot acelerado em 2026)

### `0x0668b4d29bf7609d0e8dccd81061801728e64623` — SATELLITE OTC (novo Jun 13)
- Bilateral clearing secundário: sent = received em todos os tokens
- Handles Junho 2026: D (DAR, 932 txs, 39M), XTER (439 txs, 6.8M), PARTI (64 txs), AVL, EDU, LISTA, SOLV, HOOK
- Recebe do broker principal → redistribui (não é exchange, é intermediário OTC)

---

## Estado actual — 12 Jun 2026

### PRÓXIMA SESSÃO — TAREFAS PRIORITÁRIAS
**MITO — histórico completo investigado (Jun 12):**
- MITO já está listado na Binance e Gate.io — NÃO é pré-listing
- Contract BSC: `0x8e1e6bf7e13c400269987b65ab2b5724b016caef`
- Histórico no broker 0x0d0707 BSC:
  - Ago 2025 – Abr 2026: OTC mínimo (centenas a milhares tokens/dia)
  - **15 Abr 2026**: primeiro spike (1.67M entrou, 765k saiu, 27 txs) ← ALERTA PRÉ-LISTING?
  - **18 Mai 2026**: 18.5M entrou + 5.7M saiu ← provável dia de listing ou anúncio
  - **22 Mai 2026**: 59.3M entrou + 48.2M saiu ← volume máximo (listing Binance/Gate?)
  - **26 Mai 2026**: 27.1M entrou
  - Pós-22 Mai: saídas diárias 2-9M → Binance HW14 (market making contínuo)
  - Jun 4: 37.7M ent + 34.8M saiu | Jun 6: 36M ent + 6.2M saiu (net buy 30M)
  - Jun 10: 9.3M saiu | Jun 11: 8.6M saiu (só outflows → Binance)
  - Jun 12 (hoje): 19.9M entrou + 12.4M saiu (equilibrado)
- **TGE confirmado: 28-29 Ago 2025** (Binance, MEXC, Gate.io em simultâneo)
- **Conclusão FINAL**: broker recebeu MITO no próprio dia do TGE (29 Ago = primeira tx nossa).
  NÃO há janela pré-listing. É market maker oficial desde o primeiro dia.
- Os volumes massivos de Mai 2026 (59M+) são provavelmente: token unlock, pump de preço, ou
  novo listing numa exchange adicional — NÃO é sinal insider.
- MITO fechado: caso de market making normal, sem relevância para investigação pré-listing.


1. **Cross-reference FEITO (Jun 12)** — tokens do broker que também estão no Supabase:
   COOKIE ($126M, Jun2024), AITECH ($188M, Out2023), TOKEN ($261M, Nov2023),
   SIGN ($39M, Abr2025 ⭐), HYPER ($15M, Abr2025 ⭐), LISTA ($38M, Jun2024),
   THE ($34M, Nov2024), ID ($81M), EDU ($35M)
   → SIGN e HYPER INVESTIGADOS (Jun 12) — ver secção abaixo
2. **Monitor real-time 0x0d0707 BSC** — quando altcoin desconhecido passa em volume → sinal pré-listing
   → Arquitectura: polling BSC via Alchemy/Moralis a cada 30s, filtrar por novos símbolos, alertar
3. Monitorizar saída de `0x9d9695` (2.375M GENIUS, ~$1.1M)
4. Monitorizar saída de `0xe9f1c1a3` ($1.7M USDT staging)

---

---

## Tokens pré-listing activos no broker — Jun 13 ⭐⭐⭐

### `0x055a3b37957bfbd3345bed9968e7e8dd56d67066` — NÃO é whale, é infraestrutura
- $313M USDT recebidos (1M txs), $158M WBNB, $34M USDC, $82M BNB desde Jan 2026
- Recebe TODOS os tokens desconhecidos: WARD (101.9M), SIREN (29M), AIOT (153M), SKYAI (66M), MYX (46.7M)...
- É o ponto de distribuição final do clearinghouse — router ou HW de exchange
- Tokens que acumula = pipeline de próximos listings
- **OUTFLOWS confirmados (Jun 13 2026):** o destino dominante é `0xb7697d225fa34bf1ebd3413adfa1c35b1be74729`
  - USDT: 40,670 txs → `0xb7697d225` | BULLA: 12,061 txs, 260M | OWL: 9,406 txs, 149M
  - RVV: 8,713 txs, 2.7B | LYN: 8,534 txs | AIOT: 8,372 txs, 137M | MYX: 6,786 txs
  - ESIM: 5,975 txs, 70.5M | CUDIS: 5,629 txs, 164M | WoD: 5,306 txs | HANA: 4,852 txs, 224M
  - SKYAI: 4,908 txs, 45.6M via `0xbc42145d5` | Q: 4,691 txs, 556M | BTW: 4,266 txs, 447M

### `0xb7697d225fa34bf1ebd3413adfa1c35b1be74729` — EXCHANGE SETTLEMENT HUB FINAL ⭐⭐⭐⭐⭐ [NOVO Jun 13]
**Destino dominante dos outflows de `0x055a3b37`. É o elo final da cadeia.**

Portfolio Jan-Jun 2026 (top 20 por txs):
| Token | Txs total | Received | Sent | Padrão |
|-------|-----------|----------|------|--------|
| **USDT** | **1,015,516** | **$2.244B** | **$241M** | **NET +$2B** ← acumula USDT |
| USDC | 148,232 | $35.9M | $35.7M | bilateral |
| LYN | 72,449 | 130.1M | 130.1M | bilateral |
| USD1 | 63,278 | $14.75M | $14.65M | bilateral |
| OWL | 46,783 | 325.4M | 325.4M | bilateral |
| DN | 43,351 | 24.6M | 24.5M | bilateral |
| RVV | 35,766 | 5.43B | 5.43B | bilateral |
| BTW | 31,679 | 446.3M | 446.3M | bilateral |
| CLO | 30,610 | 58.5M | 58.5M | bilateral |
| BULLA | 27,605 | 261M | 261M | bilateral |
| ARTX | 27,454 | 27.7M | 27.7M | bilateral |
| RTX | 26,908 | 4.4M | 4.4M | bilateral |
| ESIM | 25,885 | 122.5M | 122.5M | bilateral |
| AIOT | 23,714 | 137.6M | 137.6M | bilateral |
| QAIT | 20,289 | 154.7M | 154.7M | bilateral ← QAIT já listado! |

**Interpretação:**
- Received = Sent em todos os tokens → bilateral clearing puro (igual ao prime broker)
- **Net $2B USDT** → é onde vai o dinheiro de todos os OTC: exchange settlement
- 1M txs de USDT em 6 meses → ~5,500 txs/dia → só possível numa exchange major
- Handles QAIT (pós-listing Binance) com o mesmo padrão = infra de exchange
- **Conclusão: provável Binance BSC Main Settlement / Liquidity Hub**
- **Ciclo FECHADO**: Sellers → Broker `0x0d0707` → Accumulator `0x055a3b37` → **`0xb7697d225` (Binance Settlement)** → Binance Exchange

### ❌ SIREN — CRASH -90% (Jun 13/14 2026) — CASO DE ESTUDO: DUMP VIA OTC [REVISTO]
- Contract BSC: `0x997a58129890bbda032231a52ed1ddc845fc18e1`
- **Top holder controlava 82% do supply** — concentração extrema não detectada
- **SIREN plunge -90%, $760M market cap destruído, liquidações em cascata**

**Reinterpretação do que vimos no broker:**
- **198 sellers em Junho** = whales a liquidar via OTC, NÃO acumulação para listing
- **60.7M num único dia (Jun 13)** = o maior dump OTC antes do crash público
- Gate.io parou em 8 Mai 2026 = Gate.io saiu cedo, não voltou
- Destino era `0xb7697d225` (exchange settlement, venda imediata) = saída para exchange, não holding

**Modelo revisado — descoberta metodológica chave:**
> **O broker é um detector de eventos coordenados pré-listing, NÃO um detector de direcção.**
>
> Detecta que algo vai acontecer. Não distingue pump de dump.
> Os 198 senders eram todos insiders com informação privilegiada — simplesmente o evento era
> "vamos todos sair no listing" em vez de "vamos segurar para o pump."
>
> Para distinguir acumulação legítima de dump coordenado, precisamos de uma camada extra:
>
> | Sinal | Acumulação legítima | Dump coordenado |
> |-------|--------------------|-----------------| 
> | Supply concentration | distribuído | 1 holder >50% ← SIREN: 82% |
> | Destino tokens no broker | accumulator estático | exchange settlement directo ← SIREN |
> | Vol/MC ratio | normal | anormalmente alto ← SIREN: 2.7x |
> | Token age/vesting | novo, ainda a distribuir | supply concentrado há meses |
>
> Red flags no SIREN que devíamos ter pesado:
> 1. Vol $249M vs MC $92M = 2.7x → liquidez artificial para facilitar saída
> 2. Destino era `0xb7697d225` (exchange settlement directo) → saída, não holding
> 3. 82% supply num único holder → qualquer listing = oportunidade de dump
>
> A metodologia detectou a acumulação correctamente. O filtro que falta é: quem acumula e porquê.

**Arquitectura SIREN (corrigida Jun 15):**
```
Individual insiders → Prime Broker (0x0d0707) → Gate.io OTC (0xc882b111) → liquidação
```
Gate.io é DOWNSTREAM do broker para SIREN (diferente de HANA/ESPORTS onde Gate.io é fornecedor ao broker).

**Top sellers ao prime broker — todos os insiders SIREN (Jun 15) ⭐⭐⭐⭐⭐:**

Cluster Feb 22-24 2025 — **insiders mais antigos** (entraram 15+ meses antes do crash):
| Wallet | Total SIREN | Data entrada | Txs |
|--------|------------|--------------|-----|
| `0x09d6dbc9dd88f84fe21c5d4e631f5327e9b8d61a` | **18.2M** | **Feb 24 2025** | 4 |
| `0xbcc598dfafa9fd08bf85b755809a6cefeeaa16ad` | 10.1M | Feb 22-23 2025 | 2 |
| `0x5e69e571c5755951667e995a991d91bb2775ddfe` | 8.0M | Feb 22-23 2025 | 2 |
| `0x2bd2a42d914feab98b8f7310aa06792a578e7541` | 7.2M | Feb 23 2025 | 1 |
| `0xe70869c4ec42739924b5eaf029e8b3585e7a5028` | 5.6M | Feb 22 2025 | 1 |
| `0x4b4192ed7f8ea4eecff2c1d4ed0f4b904a751013` | 5.2M | Feb 23 2025 | 2 |
| `0xb1e8a131096aec643ad738f3f377c0df9a7b5195` | 5.1M | Feb 23 2025 | 2 |
| `0x1591c3b7b26c34e2462e1ea606d0e23a3b24f71e` | 5.0M | Feb 23 2025 | 1 |

Sellers recentes (activos até ao crash Jun 2026):
| Wallet | Total SIREN | Nota |
|--------|------------|------|
| `0xdd04f596` | **36.1M** | Mar 30 2025 → Jun 11 2026; também HANA 40M |
| `0x33ba873a` | 30.2M | Confirmado SIREN+HANA+ESPORTS |
| `0xc6f21469` | 20.2M | Mar 27 2025, 10 txs |
| `0x6cdf9452` | 19.7M | Mar 21 2025; confirmado SIREN+HANA+ESPORTS |
| `0xe6451016` | 16.3M | 7/7 wallet |
| `0xb85b0984` | 15.9M | 7/7 wallet |
| `0x8d17fbfb` | 14.6M | 7/7 wallet |
| `0x24a0d992` | 14.5M | 7/7 wallet |
| `0xfec3a995` | 10.7M | Mar 21 2025, parou Abr 2026 |
| `0xe5cb1895` | 10.2M | activo até Jun 13 2026 |
| `0x99aa6c28` | 9.6M | activo Jun 13 2026 |
| `0x9e4a7a68` | 9.0M | activo Jun 13 2026; também ESPORTS Jun 3 |
| `0x41cd20a8` | 6.4M | activo Jun 13 2026; também ESPORTS Jun 3 |
| `0x2004b06e` | 5.9M | activo Jun 13 2026; também ESPORTS Jun 3 |

**Sellers documentados (activos Jun 13, foram os dumpers):**
- `0xdd04f596`, `0xe5cb1895`, `0x99aa6c28`, `0x9e4a7a68`, `0x522fd166`, `0xb89baad6`, `0x41cd20a8`
- **Estes eram os dumpers, não "sellers pré-listing"**

**Sinal que devíamos ter visto:**
- 82% supply num holder = risco de concentração extremo
- Volume 24h $249M vs MC $92M (2.7x ratio) = actividade anormal de saída
- Destino: exchange settlement directo (não accumulator estático)

### `0x218c18d02f0723291ce93aa5c0e5eb709903179a` — MARKET MAKING ENGINE ⭐⭐⭐⭐⭐ [CORRIGIDO Jun 13]
**LABEL ANTERIOR ERRADO** — não é meme bot. É um market maker engine ou hot wallet de exchange de alta frequência.
- sent ≈ received em TODOS os tokens → bilateral clearing, não acumula posições
- Opera 24/7 com dezenas de tokens em simultâneo
- Top tokens por volume de txs (Jan-Jun 2026):

| Token | Txs | Volume |
|-------|-----|--------|
| RTX (RateX) | 20,838 | 2.15M |
| CRTR | 17,481 | 170M |
| ESIM | 11,499 | 69M |
| ARTX | 11,485 | 6.5M |
| **SIREN** | **11,027** | **8.7M** ← pré-listing candidate |
| BTW (Bitway) | 9,488 | 97.9M |
| XCX | 8,556 | 112.6M |
| $AIAV | 8,246 | 97.4M |
| GF | 7,727 | 327M |
| **QAIT** | **6,155** | **41.3M** ← pré-listing candidate |
| GAIN (pós-listing) | ~665 | 89.6M |

**Conclusão**: este wallet faz market making para tokens pré-listing (QAIT, SIREN) e pós-listing (GAIN) com a mesma infra.
É a infra-estrutura de market making que prepara liquidez antes do listing na CEX.
A presença de QAIT e SIREN aqui = preparação activa de liquidez = listing iminente.

### `0x4a4915a02ebfd6e05132ff9f622646d157b719bb` — SEGUNDO MARKET MAKER REAL ⭐⭐⭐⭐⭐
Recebe via broker directamente. Portfolio activo (Mai-Jun 2026):

| Token | Symbol | Contract | Txs | Total | Início | Activo |
|-------|--------|----------|-----|-------|--------|--------|
| SKYAI | SKYAI | `0x92aa0313` | 2726 | 62M | May 5 | Jun 13 ✅ |
| LAB | LAB | `0x7ec43cf6` | 1849 | 2.4M | May 2 | Jun 13 ✅ |
| SIREN | SIREN | `0x997a5812` | 1094 | 6.4M | **Jun 3** | Jun 13 ✅ |
| RIVER | RIVER | `0xda7ad9de` | 914 | 391k | May 17 | Jun 13 ✅ |
| TA (Trusta.AI) | TA | `0x539ae81a` | 889 | 39M | May 1 | Jun 3 |
| ZEST | ZEST | `0x5506599c` | 781 | 18.6M | **May 22** | Jun 12 |
| Genius | GENIUS | `0x1f12b85a` | 747 | 2.9M | May 8 | Jun 13 ✅ |
| Unitas | UP | `0x000008d2` | 649 | 9.6M | May 17 | Jun 13 ✅ |
| Quack AI | Q | `0xc07e1300` | 635 | 157M | May 1 | Jun 13 ✅ |
| MYX | MYX | `0xd82544bf` | 614 | 8.6M | May 1 | Jun 13 ✅ |
| JANCTION | JCT | `0xea37a8de` | 561 | **502M** | May 8 | Jun 13 ✅ |
| Bitway | BTW | `0x444045b0` | 519 | 34M | **Jun 5** | Jun 13 ✅ |
| Collect Fanable | COLLECT | `0x4b3d3099` | 507 | 28.5M | May 11 | Jun 12 |
| TRADOOR | TRADOOR | `0x91234004` | 412 | 2.5M | May 1 | Jun 13 ✅ |

ZEST started May 22 at this wallet → May 22 + 37 dias = Jun 28 listing estimado 🚨

### WARD (Warden Protocol) — pós-Alpha, pré-Spot ⭐⭐⭐
- Contract BSC: `0x6dc200b21894af4660b549b678ea8df22bf7cfac`
- **Binance Alpha: 4 Fev 2026** (primeiro listing, airdrop para Alpha Points)
- Outros listings: KuCoin, Bitget, Kraken, Gate.io (todos após Alpha)
- **Binance Spot: NÃO confirmado** (Jun 2026)
- Preço: ~$0.0075 | Pump 500% em Maio após fusão Warden+Venice AI
- **Broker activity Mai-Jun 2026:**
  - 18 Mai: 24 txs, 22 sellers, 8.3M in — burst inicial
  - 21 Mai: 24 sellers, 4.6M in
  - 23 Mai: 25 sellers, 6.1M in
  - 26 Mai: 18 sellers, 9.9M in (maior inflow)
  - 1 Jun: 17 sellers, 6.1M in
  - 4 Jun: 15 sellers, 10.7M in
  - 5-6 Jun: só outflows — fim de ciclo?
  - **Padrão**: inflow days (multi-seller) alternados com outflow days (1 sender)
- Padrão: sellers → broker → `0x055a3b37` + `0x218c18d0`
- **Estimativa Binance Spot**: Binance Alpha (Feb) → Spot delay médio 3-6 meses → Jul-Ago 2026
- Activity parou Jun 6 — possível que ciclo encerrado sem Spot listing (risco)

### QAIT (SEALCOIN/WISeKey) — JÁ LISTADO ⚠️ [CORRIGIDO Jun 13]
- Contract BSC: `0x997a...` (ver Supabase)
- **LISTADO em Binance + KuCoin + Gate.io + MEXC desde 28 Mai 2026**
- Actividade no broker = pós-listing OTC / vesting unlocks (NÃO é pré-listing)
- Top buyer: `0x3bc367866` — 52.7M QAIT, 1,502 txs (ver secção abaixo)
- Sellers OTC (endereços completos confirmados Jun 13):
  - `0x96973f7b83a3c785d94e0a6d8712174abb81b748` (24M QAIT, 21.3M GAIN — activo Jun 13)
  - `0x8d17fbfb03a6b7e8fdcfd60f1f9e6c08578ba5d7` (10.3M QAIT, 47.8M GAIN)
  - `0xe6451016f095835a0d5ef98a5c0092e47ddf0a93` (9.75M QAIT, 31.8M GAIN — parou Mai 4)
  - `0xb85b098448b2aac4af96f5bdd9c6c02373a08975` (44.7M GAIN)
  - `0x24a0d9928a3b6cd13a6210d0ff6d450a080fc266` (35.8M GAIN)
  - `0x016b7836331b7d0026dd99cf903bfcad41e1a189` (125.9M GAIN — maior seller individual!)
- `0x049166` — primeiro seller 28 Mai às 15:00:36, 6M QAIT (mesmo dia do listing)
- **Conclusão**: QAIT fechado — é market making pós-listing, sem valor para investigação pré-listing

### `0x3bc367866468d4f80096be899b66ab29d03f2717` — HUB OTC MULTI-EXCHANGE ⭐⭐⭐⭐ [INVESTIGADO Jun 13]
**Identidade: market maker / OTC hub de grande escala — NÃO exclusivamente Binance**

Top tokens recebidos em 2026 (inbound):
| Token | Txs | Volume |
|-------|-----|--------|
| DOGE (BEP20) | 138,431 | 510M |
| USDT | 84,708 | $706M |
| ROBO | 78,754 | 1B |
| **USD1** (Trump stablecoin) | 63,554 | $325M |
| XNY (Codatta) | 41,100 | 386M |
| **SKYAI** | 40,926 | 172M — *parou Mai 4* |
| USDC | 38,242 | $444M |
| SENT (Sentient) | 21,038 | 164M — *parou Mai 26* |
| **QAIT** | 1,502 | 52.7M — *activo Jun 13* |
| **GAIN** | 126 | 16.7M |

**Outflows principais (para onde manda):**
- `0x73a7adaba...` — DOGE, 109,223 txs (receptor dedicado de DOGE)
- `0x238a358808...` — ROBO, USD1, USDC, KITE, DGRAM (4x nos top 20) — mega hub downstream
- `0xbc42145d5...` — SKYAI, 23,994 txs, *parou Mai 4*
- `0x908ab8983...` — SIGN, 20,432 txs, *parou Mai 22* (SIGN já listado desde Abr 2025!)

**O que isto revela (correcção ao raciocínio anterior):**
1. **NÃO é só pré-listing** — SIGN listou Abr 2025, mas esta wallet continuou market making por 13 meses (até Mai 22 2026)
2. **SKYAI** — listou na Bitget em 30 Abr 2026. Outflows pararam Mai 4 (4 dias após listing). NÃO listou Binance — logo wallet não é exclusivamente Binance
3. **SENT** — listou Binance Jan 22 2026. Inflows continuaram até Mai 26 (4 meses pós-listing) = post-listing market making
4. **Conclusão**: é um **market maker ou OTC desk** que serve múltiplas exchanges (Binance, Bitget, Gate.io) — pré E pós-listing
5. Downstream vai para `0x238a358808` (82M txs USDT, clearing enorme — provavelmente Binance BSC settlement contract ou DEX router principal)

**Wallet activo Jun 13** — recebe QAIT e outros pós-listing tokens do broker

---

_(ver secção SIREN detalhada acima — Tokens pré-listing activos no broker)_

### SIGN — 9 minutos antes do listing (confirmado)
- Listing Binance: 28 Abr 2025 às 11:00 UTC
- Broker ETH primeira tx: 28 Abr 2025 às **10:50:59 UTC** (9 min antes)
- Conclusão: broker É o market maker oficial que semeia liquidez antes da abertura

### HYPER — TGE Apr 22 2025, market maker desde dia 0
- Contract BSC: `0xc9d23ed2adb0f551369946bd377f8644ce1ca5c4`
- TGE em 22 Abr 2025 (mint + distribuição às 11:00 UTC)
- Broker entrou 12:01 UTC no mesmo dia — market maker oficial desde TGE
- Spike Jul 10 ($3.3M) = listing Binance/Gate 79 dias após TGE

---

## SIGN e HYPER — Investigação completa (Jun 12)

### HYPER no broker BSC ⭐⭐⭐
- **Primeira vez no broker:** 22 Abr 2025 (12:01 UTC, 106 txs, $21k)
- Acumulação contínua: Abr 29 $244k, Abr 30 $252k, Mai 6 $560k
- **Listing provável: 10 Jul 2025** — explosão $3.3M (556 txs) + 11 Jul $2.2M (238 txs)
- **Janela pré-listing: ~79 dias** (broker viu HYPER quase 3 meses antes do listing)
- Volume continua até Ago 2025 (trading pós-listing)
- **Contract BSC confirmado:** `0xc9d23ed2adb0f551369946bd377f8644ce1ca5c4` (3141 txs, $11.8M total)
- NÃO é HyperLiquid (HYPE) — HYPE está na HyperEVM chain. HYPER BSC é token diferente.

### SIGN no broker ETH ⭐⭐
- **Primeira vez no broker:** 28 Abr 2025 (1 tx, $32 — tx teste)
- Actividade real começa: 29 Abr 2025 ($75k, 4 txs)
- Picos: Mai 6 $368k, Mai 9 $421k, **Mai 23 $1.12M** ← provável listing 1
- Segundo ciclo: **Set 23-25 2025** ($385k + $522k + $645k) ← provável listing 2 (Gate.io/OKX?)
- SIGN está no ETH, não BSC — os "SIGN" na BSC são tokens falsos/scam (vários contracts diferentes, USD=null)
- **Janela pré-listing (estimada): ~25 dias** (abr 28 → mai 23)
- Verificar data exacta de listing Binance para confirmar se broker chegou primeiro
- Sign Protocol SIGN ETH contract: a confirmar (query broker ETH só confirma símbolo, não contract)

### Padrão confirmado em 3 casos (GENIUS, HYPER, SIGN):
  Broker processa token → semanas/meses depois → listing na Binance → explosão de volume
  GENIUS: 39 dias | HYPER: ~79 dias | SIGN: ~25 dias (estimado)

---

## Estado actual — 11 Jun 2026

### Caso principal: GENIUS (Binance listing 22 Mai 2026)

**Cluster identificado:** gianmarco_eth + TaiwanNumbaWan + Geniusmoon

**Fluxo reconstruído:**
1. **Abr 13-14:** Ghost Order Hub (0x199a74) comprou 2.377M GENIUS a 9 sellers BSC em OTC, pagou $52k USDC
2. **Abr 16:** Consolidou para gianmarco_eth (0xD8BDd8)
3. **Mai 28-29:** Teste round-trip via relay wallet (~1,009 GENIUS vendidos)
4. **Jun 9:** 2.375M GENIUS → holding wallet 0x9d9695 (~$1.1M ao preço actual de $0.47) — **zero saídas**

**Ficheiro de labels:** `C:\Users\joser\OneDrive\Área de Trabalho\labbel\1.txt` (Entity 14)

---

## Rede OTC BSC — mapa completo (atualizado Jun 11 — final)

```
CAMADA 0 — ORIGEM FINAL
  0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23
       |  $999k USDT (Jun 11)
       v
  0xbcf6011192399df75a96b0a4ce47c4820853e9e5  (245k txs — P2P distributor)
       |-- Mai 31: $1M → staging 0xe9f1c1a3 → 0x128463
       |-- Jun 11: distribui $5-25k a 15 wallets pequenas

CAMADA 1 — MARKET-MAKING BILATERAL
  0x144d395b5562c742259932d2ee6e1d8d092a21b8  (935k txs)
       <---> 0xa50c4fe8c8a0a47872c378c11cf7f6ea1780ff7b  (441k txs)
             + 0x3fe7b866182aab8c8057... (121 txs bilateral com 144d)
  Trocam USDT/USDC/USD1 back-and-forth (market making de stablecoins)
  0xa50c4fe8 feeds OTC desks downstream

CAMADA 2 — OTC ROUTING DESKS (já mapeados)
  [ver secção anterior]

CAMADA 3 — GENIUS OTC CAPITAL (TW_vanity2 → GhostOrderHub)
  [ver secção anterior]
```

## Rede OTC BSC — mapa completo (atualizado Jun 11)

```
CAMADA 0.5 — OTC CORE INFRASTRUCTURE (descoberto Jun 13) ⭐⭐⭐⭐⭐
  4 wallets que são a espinha dorsal de TODA a rede:
    0xdf8a3e85e14ae2f143f3d204b421b813e5fe5978  ← maior GAIN seller (67M); também SIREN, ION, elizaOS
    0xdd3cb5c974601bc3974d908ea4a86020f9999e0c  ← GAIN regular (38M); SIREN, WoD, memes
    0x4982085c9e2f89f2ecb8131eca71afad896e89cb  ← GAIN regular (16M); SIREN, SKYAI, OWL
    0x53f78a071d04224b8e254e243fffc6d9f2f3fa23  ← GAIN (6M); SIREN, elizaOS

  Volume USDT combinado em 2026: $11 MIL MILHÕES
  Tokens que passam por estes wallets: USDT, BULLA, CRTR, LYN, SIREN, WoD, elizaOS,
    memes, RVV, ION, OWL, SKYAI, DONKEY, GAIN — TODOS os tokens da rede passam aqui
  → NÃO são insiders específicos do GAIN; são a INFRA-ESTRUTURA OTC CORE de toda a operação
  → SIREN (578M txs, 26k txs) e SKYAI (302M, 14k txs) passam pelos mesmos wallets = mesma rede

CAMADA 1 — FONTES DE CAPITAL
  0x144d395b5562c742259932d2ee6e1d8d092a21b8  (146 txs bilateral com 0xa50c4fe8)
       |
       v
  0xa50c4fe8c8a0a47872c378c11cf7f6ea1780ff7b  (441k txs — capital hub primário)
       |
       |-- directamente -> OTC_238a35 (76 txs)
       |-- directamente -> OTC_28e2ea (7 txs)
       |-- via passthru:
            0x982f8a06dcce09f5819179b3645690919733fda9  (passthru, 107k txs)
                  -> OTC_238a35 ($3.46M/dia em chunks $50-100k USDT/USD1)

CAMADA 2 — OTC ROUTING DESKS
  OTC_partner_238a35  (0x238a35)  ← $3.46M+/dia USDT/USDC/USD1
  OTC_partner_28e2ea  (0x28e2ea)  ← $1M+/dia USDT
  0x128463 (consolidation hub, 300k txs)
       ← 10× wallets $45k simultâneo
       → 0xe9f1c1a3 ($1.7M staging hoje, ainda não movido!)
       ↔ TW_vanity2 (bilateral; envia $97k hoje)

CAMADA 3 — FINANCIAMENTO DO GENIUS OTC
  TW_vanity2 (0x87b11c...bab1074)  ← COFRE CENTRAL
       ← $349k de aggregator_6cfc3f (Abr 12)
       ← $10k de gianmarco_eth (Abr 12)
       ← $11k de seller G (Abr 12)
       → $406k USDT → GhostOrderHub (Abr 13) → GENIUS OTC

CAMADA 4 — GENIUS ACCUMULATION
  GhostOrderHub (0x199a7443) → compra 2.377M GENIUS de 9 sellers BSC
  → gianmarco_eth → holding 0x9d9695 (~$1.1M, zero saídas)
```

## Rede OTC BSC — mapa (versão anterior)

A rede pre-existe ao GENIUS (operacional desde pelo menos Mar 2026) e está **activa hoje**:

```
0xb300000b (router/aggregador BSC)
0x4783310f, 0x28b756, 0xbc7ce4 (feeders)
      │
      ▼
0xcd8d805a ──────────────────► OTC_partner_28e2ea (0x28e2ea)
(pass-through, 11.7M txs total)   ├─► 0xaab97580 ($10k chunks)
                                   └─► 0x55996427 ($10k chunks)

0x52aa8994 (swap desk USDC↔USDT, 838k txs, usa 1inch)
  └─ serve 238a35, serve USDC_payout_b45369 (ainda hoje)

OTC_partner_238a35 (0x238a35)
  └─ 0x982f8a06 → $80k USDC
  └─ swap USDC/USDT com 0x0f0067cd
  └─ $1M+ USDT/USDC por dia

sellerD (0x70ab0ed7) — OTC desk $1M+/dia, pre-existente
sellerA (0x3d90f66b) — ACTIVO HOJE na rede OTC
```

**Link TaiwanNumbaWan confirmado:**
- Seller G (0xfe94b33f) enviou $740 BNB + $936 USDT a TaiwanNumbaWan 2 dias antes do OTC de GENIUS
- 0x6cfc3fd9 agrega pagamentos → sweep para `0x87b11c5c...bab1074` (mesmo prefixo vanity que TaiwanNumbaWan)

---

## Descobertas da sessão Jun 11 — tarde

### TW_vanity2 (0x87b11c...bab1074) = COFRE CENTRAL da operação ⭐⭐⭐

```
Abr 12: Recebe de gianmarco_eth (0xd8bdd8) $10,197 USDT — LIGAÇÃO DIRETA
Abr 12: Recebe de 0x6cfc3fd9 (aggregator) $349k USDT
Abr 12: Recebe de seller G $11k USDT + 1.25 BNB
Abr 12: Recebe de outras fontes $22k USDT
Abr 13: ENVIA $405,542 USDT → Ghost Order Hub (0x199a7443) ← FINANCIA O OTC
Abr 13: ENVIA $1,000 USDT + 1.25 BNB → Ghost Order Hub
Jun 11: Recebe $97k USDT de 0x128463 — ainda activo
```
**Esta wallet bancou o GENIUS OTC.** Não é coincidência de prefixo vanity — é o braço financeiro de gianmarco_eth/TaiwanNumbaWan.

### 0x128463 = OTC Consolidation Hub (300k txs)
- Recolhe $45k de 10+ wallets em simultâneo
- Sweep de $1.7M USDT para `0xe9f1c1a39ba8221a3f` num único tx
- Bilateral com TW_vanity2 (envia $97k hoje)

### 0x982f8a = pass-through $3.46M/dia
- `0xa50c4fe8c8a0a47872` → `0x982f8a` → `OTC_partner_238a35`
- Chunks de $50k-$100k em USDT/USDC/**USD1 (Trump stablecoin!)**
- 107k txs total

### Nota: USD1 (World Liberty Financial / Trump) em uso nesta rede

## Wallets pendentes de analisar [ACTUALIZADO Jun 16 — ver descobertas abaixo]

| Wallet | Prioridade | Motivo / Estado |
|--------|-----------|--------|
| `0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23` | ✅ RESOLVIDO Jun 16 | **NÃO é "origem $999k" — é MEGA-HUB $40.2B USDT** (ver descobertas Jun 16 abaixo) |
| `0xe9f1c1a39ba8221a3ffe3a6bb41f943b3075892a` | ✅ RESOLVIDO Jun 16 | **NÃO está parado com $1.7M — é pass-through net-zero $3.13M** (ver abaixo) |
| `0x3fe7b866182aab8c805769747663b3046541c4d6` | 🟡 Media | 121 txs bilateral com 0x144d395b (trinca de market-making) |
| `0x8a289d458f5a134ba40015085a8f50ffb681b41d` | 🟡 Media | Feeder de 0x6cfc3fd9 — timeout no Dune (wallet enorme) |
| `0x9d9695c225d566d77848c19f4728f62a5466e68a` | ✅ Jun 16 | Holding 2.375M GENIUS — **ZERO saídas desde Jun 8, ainda segura** (não dumpou) |
| `0x6a0da4bf7c7861e4ef8a114072d2d77b8df45640` | 🟢 Baixa | GENIUS LP/router usado por seller B pós-OTC |

### ⚡ DESCOBERTAS GENIUS — sessão Jun 16 (Opus deep dive) ⭐⭐⭐⭐⭐

**1. `0x1ab4973a` = MEGA-HUB USDT de $40.2 MIL MILHÕES (não "origem $999k")**
- USDT real (contrato `0x55d398...`): IN 13,786,443 txs / **$40.225B** | OUT 5,219,180 txs / **$40.187B**
- Activo desde Jan 9 2024 até **HOJE Jun 16 2026 19:18 UTC** (~15k txs/dia)
- Escala de hot wallet de exchange major ou treasury de market-maker de topo
- Funil recorrente para a rede GENIUS: `0x1ab4973a` → `0xbcf60111` ($18M só Jun 14-16)
- Maior contraparte recente nova: `0x26209d9f0dc3ac0129c3fb1badabfeb9ee728c66` ($64M, Jun 14-16)
- **A sessão anterior subestimou-o brutalmente. É o verdadeiro apex de capital da rede.**
- **Fingerprint Jun 16:** recebe o MESMO cabaz pré-listing que o broker — SAHARA (5337 txs), ASTER,
  BTW, SKYAI, VELVET (2287), MYX, XTER (710), GENIUS (408), RIVER, CROSS, RVV... Não é só USDT,
  processa todos os tokens da rede = infra de exchange/MM, não wallet retail
- **NÃO tem transferências USDT directas com a Binance Treasury conhecida `0x238a358808`** (0 txs)
  → hub funcionalmente SEPARADO do cluster Treasury já mapeado
- **❌ FINGERPRINT DE MARCA (Jun 16) ESTAVA ERRADO** — dizia "BINANCE" pelo spam 币安. INVÁLIDO:
  o spam é controlado pelo emissor, não prova nada. (Idem o "OKX" de 0x4e7ed91e baseado em 欧易.)
- **ALIMENTA a rede do broker:** envia VELVET → Main Accumulator `0x055a3b37` (195 txs, 97.6k).
  É simultaneamente apex de CAPITAL (financia GENIUS via 0xbcf60111) E FONTE dos tokens Alpha.
- **✅ CONCLUSÃO CORRIGIDA Jun 17 (Arkham API) → É BITGET, NÃO Binance.** Trace Arkham:
  inbound $50.6B de Bitget main 0xffa8DB7B + centenas "Bitget Deposit"; cluster ambas direcções
  100% Bitget (0xaDFffc33, 0x26209d9f, 0x70213959). Hot/omnibus wallet Bitget BSC. Continua a
  ser apex de capital do broker, mas a exchange é Bitget. Lição: usar SEMPRE labels Arkham.

**2. `0xe9f1c1a3` CORRECÇÃO — não é "$1.7M staging parado", é pass-through net-zero**
- USDT real: IN 26 txs / $3.127M | OUT 9 txs / $3.127M (net ~0). Última actividade real Jun 12.
- Rasto real do dinheiro: Mai 31 → $1.0M para `0x128463` (consolidation hub) | Jun 12 → $2.13M para `0xfe05e1403286d629203181173a24680f0379a52c`
- `0xfe05e140...a52c` é também pass-through: recebeu $2.13M e reenviou tudo 4min depois → de volta a `0x1ab4973a` (loop fecha no apex)
- **A leitura anterior "$1.7M parado, monitorizar saída" estava ERRADA** — já tinha ciclado.

**3. ⚠️ ADDRESS POISONING activo a impersonar `0xe9f1c1a3`** (técnica anti-tracing)
- Spam de "USDT" FALSO (símbolos unicode spoofados: " U5DТ ", "U឵S឵DΤ" com cirílico) + transferências zero-value no contrato USDT real
- Destinos-engodo partilham prefixo `0xfe05` + sufixo `a52c` (`0xfe05abd0...a52c`, `0xfe05c0c0...a52c`) para imitar o destino real `0xfe05e140...a52c`
- Objectivo: levar um analista descuidado a copiar o endereço errado
- **REGRA: ao traçar esta rede, filtrar SEMPRE por contrato USDT real `0x55d398326f99059ff775485246999027b3197955` e ignorar símbolos spoofados e amounts=0**

**4. `0x9d9695` (GENIUS holding) — confirmado NÃO dumpou**
- Zero outflows em ETH desde Jun 8. Os 2.375M GENIUS continuam parados (gianmarco_eth profit).

---

## Supabase — token_prelisting_wallets

82 tokens scaneados. Casos com maior volume suspeito:

| Token | Exchange | Listing | Wallets | Max in |
|-------|----------|---------|---------|--------|
| EIGEN | OKX | 2024-10-01 | 6 | $996M |
| LAYER | OKX | 2026-02-05 | 13 | $981M |
| KAITO | Binance | 2025-03-10 | 13 | $426M |
| SIGMA | OKX | 2024-10-05 | 8 | $239M |
| H | OKX | 2026-05-19 | 8 | $99M |
| EDGE | OKX | 2026-05-06 | 10 | $90M |
| AI16Z | OKX | 2024-12-20 | 14 | $92M |
| BERA | OKX | 2025-02-06 | 1 | $123M |
| NEIRO | Binance | 2024-09-05 | 13 | $68M |
| DEGEN | OKX | 2024-04-15 | 18 | $59M |

> **Próximos a investigar:** EDGE, H, LAYER, EIGEN — volumes muito altos, poucos wallets

---

## Decisões tomadas

- **Dune Analytics** para dados BSC/EVM crus (gratuito, evita gastar Arkham API tokens)
- **Arkham** só para labeling de wallets já identificadas por Dune
- **Scripts locais** `backend/worker/_parse_dune*.py` — NÃO para GitHub
- **NADA da investigação GENIUS vai para GitHub** (endereços, scripts, outputs)
- Tokens CFTC (GOAT, FWOG, ACT, MEW, MOTHER) — não submeter ao Arkham

---

## Descobertas sessão Jun 12 — 0x0d0707 = PRIME BROKER GLOBAL ⭐⭐⭐⭐⭐

### 0x0d0707963952f2fba59dd06f2b425ace40b492fe — escala real

Label CFTC dossier: "Gate.io Deposit ETH" — PROVÁVEL LABEL ERRADO ou é o OTC desk interno da Gate.io.

**Volume ETH (2024–2026): >$30B**
**Volume BSC (2026 só): >$3B**

Principais contrapartes ETH (bilaterais $3-5B cada):
- `0x42a178633240601d3485e1f51d8b62ea58c9b5ae`: envia $5.35B USDT + $1.82B ETH → 0x0d0707
- `0x32d03f46ba2857c8e6a920ab3fed1f24d35d85d1`: recebe $5.1B USDT + $895M USDC + $475M ETH de 0x0d0707
- `0xc882b111a75c0c657fc507c04fbfcd2cc984f071`: bilateral $3.9B USDT + $2.9B ETH (+ $517M ONDO IN / $449M ONDO OUT)
- `0x6455327f820edd69c4cd665b995e0fec679d7f9e`: envia $3.8B ETH + $3.4B USDT → 0x0d0707
- `0xeae7380dd4cef6fbd1144f49e4d1e6964258a4f4`: recebe $3.4B ETH de 0x0d0707

BSC top counterparts 2026:
- `0x32d03f46` (mesmo endereço do ETH!): $1.27B USDT+BTCB+ETH
- `0xc882b111` (mesmo endereço do ETH!): $368M USDT OUT / $334M+$143M BNB IN
- `0x2d6ffec3acbdaff0f895e70fcc699246a2798102`: $374M USDT + $166M ETH saem
- `0x8931d1be968b4f3a8391f9d6a518fc990062a607`: $286M USDT + $189M BTCB entram

ONDO link: `0x769e4e225da686986d8ddc8bcd4fa8d3bf046a60` envia $336M ONDO → 0x0d0707
(mesmo prefixo 0x769e4e225 que vendeu 19M MITO via BSC — mesma entidade cross-chain)

Tokens na BSC 2024: USDT, ETH, COOKIE, AITECH, TOKEN (pré-listings)
Tokens na ETH 2026: ETH, USDT, USDC, PAXG, XAUt, STG, EIGEN, ONDO, ENA, LINK, QNT,
                    SPYon, NVDAon, HOODon, LLYon (stocks tokenizados!), DENT, ORBS, XCN

IDENTIDADES CONFIRMADAS (Jun 12):
- `0xc882b111a75c0c657fc507c04fbfcd2cc984f071` = GATE.IO
  Prova: envia $129M GT (GateToken) em Jan 20 2026 para 0x76bbb8d5
  Faz liquidações diárias automáticas com 0x0d0707 às 04:26-04:36 UTC
  Tokens: ONDO, ENA, PEPE, SHIB, FLOKI, TURBO, LINK, FET, UNI, NEIRO, Mog, USD1, USDe

- `0x32d03f46ba2857c8e6a920ab3fed1f24d35d85d1` = Relay → BINANCE ETH HW
  Recebe de 0x0d0707, forward 10-15min depois para 0x28c6c06 (Binance ETH Hot Wallet)
  $5.1B USDT + $474M ETH + $237M USDC passam por aqui

- `0x28c6c06298d514db089934071355e5743bf21d60` = BINANCE ETH HOT WALLET
  Destino final de toda a liquidez do OTC. Também alimenta 0x42a178633 ($830M USDT)

- `0x42a178633240601d3485e1f51d8b62ea58c9b5ae` = Binance aggregator → 0x0d0707
  Recebe de Binance ($830M USDT), de múltiplos feeders (~$1B cada)
  Envia $5B USDT + $1.5B ETH + $1.2B USDC → 0x0d0707

ESTRUTURA CONFIRMADA:
  Binance HW ETH ←→ 0x42a178633 → 0x0d0707 (PRIME BROKER) ←→ 0xc882b111 (Gate.io)
                                        │ → 0x32d03f46 → Binance HW ETH
  Na BSC: 0x0d0707 = OTC multi-token desk → Binance HW14

GATE.IO — ESTRUTURA COMPLETA CONFIRMADA:
  0x1c4b70a3968436b9a0a9cf5205c787eb81bb558c = Gate.io Main Hot Wallet
    - Envia $391M GT → cold storage 0x76bbb8d5 (Jan 20 2026)
    - Envia altcoins → 0x0d0707 desde 2023: RNDR $16.8M, USDT $7.1M, OM $4.6M,
      OKB $2.4M (!), AGLD, BIT, DAO, FTM, CHZ, WOO, DYDX, ENJ, ALICE, OCEAN...
    - Recebe $151M GT de 0x9bbe47fe (GT source/rebalance)
  0xc882b111 = Gate.io OTC Desk (liquidações diárias 04:26 UTC com 0x0d0707)
  0x76bbb8d5 = Gate.io GT Cold Storage (recebeu $520M GT em Jan 20, nunca enviou)
  0x9bbe47fe = Gate.io GT treasury/source

EXCHANGES CONFIRMADAS NO PRIME BROKER (Jun 12 — final):
  GT  (Gate.io)    — bilateral $3.9B com 0xc882b111 + altcoins de 0x1c4b70a3
  OKB (OKX)        — Gate.io enviou 10k OKB → broker; broker redistribuiu 91k OKB ($17.6M)
  CRO (Crypto.com) — trading diário contínuo, múltiplos feeders → 0x0051cc1d (Crypto.com deposit?)
  BIT (Mantle)     — $1.3M via Gate.io main HW
  WOO (WOO Network)— bilateral regular
  + Binance ETH HW (0x28c6c06) via relay 0x32d03f46
  + Binance BSC HW14 (0x8894e0a0) via 0x9e56fde3

CONCLUSÃO: este prime broker é o clearinghouse das 4 maiores exchanges asiáticas
(Binance, Gate.io, OKX, Crypto.com) em simultâneo.
Qualquer pré-listing que passe por esta infra tem exposição potencial a insiders nas 4.

0x9bbe47fe = Gate.io GT cold vault (1 tx: $151M GT → 0x1c4b70a3 em Jan 20 2026)

IMPLICAÇÃO: Gate.io e Binance partilham infra de settlement via este prime broker.
Tokens pré-listing processados aqui têm visibilidade potencial em ambas as exchanges.

---

## Descobertas sessão Jun 12 — MAPA COMPLETO DA HIERARQUIA

### HIERARQUIA COMPLETA — Jun 12 ⭐⭐⭐

```
0xffa8db7b38579e6a2d14f9b347a9ace4d044cd54  ← APEX REAL (broker institucional multi-asset)
    Opera: WBTC, ETH, stETH, PAXG/XAUt (ouro), ENA, ARB, AIXBT, USD1, USDC, BNB
    Chains: ETH, BSC, Base, Optimism, Arbitrum, Sonic, Polygon, Worldchain
    Parceiros: 0x0639556f (BTC desk), 0x5bdf85216e (stETH/BTC), 0x97b9d2 (AIXBT)
    Liquidez diária: provavelmente $50-100M+
        │
        ↓  ($10-20M/burst)
0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23  ← APEX BSC (broker regional, 8 chains)
    Opera: USDT, USDC, USD1, ETH, HYPE, WLD, ENA, ONDO, USDe
    Cadeia: BSC, ETH, Polygon, Arbitrum, Optimism, Plasma, Sonic, Worldchain, HyperEVM
    Liquidez diária: $20-50M+
        │
        ├── USDT path ──► 0xbcf60111 ──► 0x128463 (USDT desk, 300k txs)
        │                                     ──► 0x79ec68d3 ──► 0x9e56fde3
        ├── USDC path ──► 0xb0e20db8 ──► 0x318d2aae (USDC desk, $575M/6sem)
        │                                     ──► 0x9e56fde3
        ├── Multi-asset ► 0x0d0707 (USDT+USDC+USD1+altcoins: MITO, SIREN, RACA...)
        │                     ──► 0xa747a91 + 0xb0e20db8 ──► 0xef3aeff9 ──► 0x9e56fde3
        └── Outros ──────► 0x276158be, 0xd0186fbb (recebem de Binance, devolvem a Binance!)
                                │
                                ↓
                     0x9e56fde394c37a (aggregator final)
                                │
                                ↓
              0x8894e0a0c962cb72 = BINANCE HOT WALLET 14
```

**Volume estimado: $1B+/mês através desta infra toda**

### Loops circulares confirmados (arbitragem Binance)
- `0xa747a91`: recebe de Binance HW14 → envia para 0x318d2aae → volta para Binance
- `0xd0186fbb`: recebe de Binance HW14 → envia para 0x318d2aae → volta para Binance
- `0x276158be`: recebe de Binance HW14 → envia para 0xef3aeff9 → volta para Binance
Esta é arbitragem/market-making: Binance paga em USDC, desk faz OTC, recebe USDT, deposita em Binance

### MITO token — acumulação massiva em curso (ALERTA PRÉ-LISTING)
Padrão claro de compras periódicas grandes:
- Mai 22: +59.3M MITO entrou no OTC
- Mai 26: +27.1M, Mai 18: +18.5M
- Jun 4: +37.7M, Jun 6: +36M
- Jun 12 (agora): +19.9M a entrar, só 2.5M saiu
Contract MITO: `0x8e1e6bf7e13c400269987b65ab2b5724b016caef`
OTC market maker: OTC_238a35 (`0x238a35`) + OTC desk `0x0d0707`
**Padrão indica listing iminente — vale correr prelisting scanner no Arkham**

---

## Descobertas sessão Jun 12 — madrugada (actualizado)

### MAPA COMPLETO DA REDE — Jun 12 ⭐⭐⭐

```
0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23   ← APEX CAPITAL (Camada 0)
    │
    ├─ USDT side ──► 0xbcf60111 (P2P dist, 245k txs)
    │                     └─► 0x128463 (USDT OTC desk, 300k txs)
    │                               └─► 0x79ec68d3 (relay, segundos)
    │                                         └─► 0x9e56fde3 ──► BINANCE HW14
    │
    ├─ USDC side ──► 0xb0e20db8 (relay USDC, ~$440k/tx)
    │                     └─► 0x318d2aae (USDC OTC desk, $575M+/6sem)
    │                               └─► 0x9e56fde3 ──► BINANCE HW14
    │
    └─ 0x0d0707963952f2 (multi-token desk: USDT+USDC+USD1+altcoins)
              └─► 0xb0e20db8 ──► 0x318d2aae ──► 0x9e56fde3 ──► BINANCE HW14
              └─► 0x9e56fde3 directamente

GENIUS link: 0x1ab4973a → 0xbcf60111 → 0x128463 → TW_vanity2 → GhostOrderHub → 2.375M GENIUS
```

Volumes confirmados (6 semanas, top 20 sources só no USDC desk):
- 0x318d2aae USDC desk: ~$575M+ em USDC
- 0x9e56fde3 → Binance: $16M só em 48h (Jun 10-12)
- Estimativa total rede: **>$1B/mês**

### OTC_238a35 é market maker universal
- OTC_partner_238a35 (`0x238a35`) faz bilateral trading de: USDT, USDC, USD1, **MITO**, e muitos outros
- É o hub de market-making para todos os tokens que passam por esta rede

### Address Poisoning attacks detectados em TODA a rede
- Atacantes criam endereços com unicode lookalikes (Lisu, cirílico, cambojano, invisíveis)
- Monitorizam cada wallet em tempo real e injecting fake tokens com mesmo amount
- `0xb0e20db8` recebe fake `ꓴꓢꓓC ` → tenta confundir `0x318d2aae` com `0x318da81c`
- `0x79ec68d3` recebe fake `UṢDT` → tenta confundir com outro endereço similar

### MITO token — venda em curso (Jun 12 01:10 UTC)
- `0x769e4e225` vendeu 19M MITO a 0x0d070796
- Múltiplos wallets vendendo MITO em simultâneo via OTC_238a35
- MITO contract: `0x8e1e6bf7e13c400269987b65ab2b5724b016caef`
- Destino final: Binance via `0x084a97d8` → 0x8894e0a0

---

## Descobertas sessão Jun 12 — madrugada

### DESTINO FINAL DA REDE OTC = BINANCE HOT WALLET 14 ⭐⭐⭐

```
0x128463 (OTC hub)
  → 0x79ec68d3 (relay, pass-through em segundos)
    → 0x9e56fde394c37a9abdc5036ec8e6f6fa8f384c30 (aggregator)
      → 0x8894e0a0c962cb723c1976a4421c95949be2d4e3  ← BINANCE HOT WALLET 14
```

Volumes para Binance via esta chain (2 dias):
- Jun 10: ~$6M (USDC/USDT)
- Jun 11: ~$8.9M (USDC/USDT)
- Jun 12 00:18 UTC: $800k USDT

**~$16M em 48h depositados em Binance por esta rede.**

Outros feeders de 0x9e56fde3:
- 0x318d2aae4c99c2e74f7b5949fa1c34df837789b8 (USDC, $1M-$3M/tx)
- 0xef3aeff9a5f61c6dda33069c58c1434006e13b20 (USDT, $1.2M)
- 0x0d0707963952f2fba59dd06f2b425ace40b492fe (USDT, $500k-$1M)
- 0x2ae1652aaef210d694db279e13a7305467d14e03 (USDT, $1.065M)

### Address Poisoning detectado
- 0x79ecfba80d24eff64c69ff1e3cf38dc7bd88bcad — copia prefixo de 0x79ec68d3
  Envia "UṢDT" (unicode fake) para confundir operadores

### Estado wallets chave Jun 12 02:24 UTC
- 0x9d9695 (GENIUS holding 2.375M) — ZERO saídas, ainda acumulando
- 0xe9f1c1a3 ($1.7M staging) — ZERO saídas, parado desde Jun 11

---

## `0x218c18d0` — multi-token market maker (JANELA PRÉ-LISTINGS) ⭐⭐⭐

Este wallet acumula 12+ tokens pré-listing via broker `0x0d0707`. É o melhor indicador de listings futuros.

Tokens identificados (por txs recebidas, 2026):

| Token | Symbol | Contract | Txs | Activo | Início |
|-------|--------|----------|-----|--------|--------|
| RateX | RTX | `0x4829a1d1` | 11398 | Jun 12 | Jan 1 |
| CREATOR | CRTR | `0xb150e91c` | 8742 | Jun 12 | Feb 24 |
| River | RIVER | `0xda7ad9de` | 7194 | Jun 2 | Jan 2 |
| Ultiland | ARTX | `0x81057438` | 5858 | Jun 12 | Jan 2 |
| DEPINSIM | ESIM | `0x7765a659` | 5682 | Jun 12 | Jan 6 |
| SIREN | SIREN | `0x997a5812` | 5519 | Jun 12 | Jan 3 |
| Everlyn | LYN | `0x302dfaf2` | 5185 | May 27 | Jan 1 |
| memes | memes | `0xf7454880` | 4854 | Jun 12 | Jan 22 |
| Bitway | BTW | `0x444045b0` | 4743 | Jun 11 | Mar 3 |
| Xeleb AI | XCX | `0xe32f9e8f` | 4270 | Jun 12 | Jan 1 |
| AI AVatar | AIAV | `0x76cc9e53` | 4076 | Jun 12 | Jan 3 |
| GoldFinger | GF | `0x6db461da` | 3860 | Jun 12 | Mar 7 |

ATENCAO [SUPERADO Jun 13]: esta nota antiga dizia que 0x218c18d0 era "bot de meme coins" e
"não é market maker pre-listing" — interpretação inicial errada baseada em dust/spam amounts
misturados com tokens reais. **Correcção Jun 13**: confirmado como Market Making Engine
⭐⭐⭐⭐⭐ de alta frequência (ver secção "Identidades confirmadas" mais acima e linha ~193) —
opera 25+ tokens reais em simultâneo, distintos do ruído de spam desta lista antiga.

---

## LISTA COMPLETA PRE-LISTINGS ACTIVOS NO BROKER ⭐⭐⭐⭐⭐ (Jun 12)

Confirmados via broker→0x055a3b37, 100% amount_usd=NULL (nenhum listado ainda):

| Symbol | Contract | Txs | Inicio broker | Activo |
|--------|----------|-----|--------------|--------|
| AIOT (OKZOO) | `0x55ad16bd` | 6201 | Jan 4 | Jun 12 ✅ |
| LAB | `0x7ec43cf6` | 3817 | Jan 1 | Jun 3 |
| SKYAI | `0x92aa0313` | 3041 | Jan 1 | Jun 12 ✅ |
| MYX | `0xd82544bf` | 2772 | Jan 1 | Jun 12 ✅ |
| ??? | `0xeccbb861` | 2327 | Mar 10 | Jun 12 ✅ SEM SIMBOLO |
| DN (DeepNode) | `0x9b6a1d4f` | 2260 | Jan 9 | Jun 12 ✅ |
| TA (Trusta.AI) | `0x539ae81a` | 2174 | Jan 1 | Jun 12 ✅ |
| FOREST | `0x11cf6bf6` | 2139 | Jan 2 | Jun 12 ✅ |
| R2 | `0x223a20e1` | 2120 | Mar 31 | Jun 12 ✅ TGE Mar 9 |
| BLESS | `0x7c821751` | 2104 | Jan 1 | Jun 12 ✅ |
| AIA | `0x53ec33cd` | 2087 | Mar 25 | Jun 12 ✅ |
| GF (GoldFinger) | `0x6db461da` | 2052 | Mar 7 | Jun 12 ✅ |
| BTG (Bitgold) | `0x4c9027e1` | 1913 | Jan 1 | Jun 12 ✅ |
| ST | `0x70be4066` | 1892 | Apr 16 | Jun 12 ✅ mais recente |
| SIREN | `0x997a5812` | 1800 | Jan 31 | Jun 9 |
| STRIKE | `0x2aa89a01` | 1481 | Mar 7 | Jun 12 ✅ |
| TRADOOR | `0x91234004` | 1480 | Jan 1 | Jun 12 ✅ |
| B | `0x6bdcce4a` | 1465 | Jan 1 | Jun 11 |
| EVAA | `0xaa036928` | 1452 | Jan 1 | Jun 12 ✅ |
| UB | `0x40b8129b` | 1402 | Jan 1 | Jun 12 ✅ |

## CALENDARIO DE LISTINGS ESTIMADO ⭐⭐⭐⭐⭐ (actualizado Jun 13)

| Token | Broker entry | Estimativa listing | Padrao | Status Jun 13 |
|-------|-------------|-------------------|--------|--------------|
| WARD | May 18 | **Jun 24** | GENIUS 37d | ACTIVO 12:18 UTC ✅ |
| ZEST | **May 19** | **Jun 25** | GENIUS 37d | ACTIVO 10:46 UTC ✅ |
| QAIT | May 28 | ~~Jul 4~~ ❌ JÁ LISTADO 28 Mai | GENIUS 37d | Confirmado Jun 13 — ver secção QAIT |
| ST | Apr 16 (TGE Apr 15) | **Jul 3** | HYPER 79d | ACTIVO Jun 13 ✅ |
| BTW (Bitway) | Jun 5 | **Jul 12** | GENIUS 37d | ACTIVO Jun 13 ✅ |
| R2 | Mar 31 (TGE Mar 9) | ? | - | ACTIVO Jun 12 |
| SIREN | Jan 31 | ? | Gate.io | Jun 9 |

Notas:
- WARD tem 13.4M tokens circulando em 30h (Jun 12-13) — muito activo
- QAIT tem 9.2M tokens em 30h — muito activo  
- ZEST tem 444k tokens em 30h — mais calmo
- ZEST broker entry May 19 (0xba615538: 5M + 0xfb770638: 3M)
  0xfb770638 tambem vendeu R2 ao broker — insider serial, monitorizar
- QAIT accumulator: 0x3bc367866468d4f80096be899b66ab29d03f2717 (novo wallet, nao visto antes)
- **CORRIGIDO Jun 16: NÃO há colisão ST/QAIT.** A estimativa "QAIT Jul 4" ficou desactualizada
  — QAIT já estava confirmado LISTADO desde 28 Mai 2026 (Binance/KuCoin/Gate.io/MEXC, ver secção
  QAIT abaixo, corrigido Jun 13). Só ST permanece como estimativa genuína não confirmada (Jul 3).

### R2 — timeline
- TGE: Mar 9, 2026 (mint 1B tokens para 0x97bd506a)
- Broker entry: Mar 30 (21 dias apos TGE)
- Sellers: 0xfb770638 (10M), 0x51dd0be8 (4M), 0x20f10479 (5M) + 15 wallets Apr 4 19:00 UTC
- Activo Jun 12

### Unknown 0xeccbb861 — RESOLVIDO Jun 16: é TOKEN CONTRACT, não wallet ⭐⭐⭐
- Endereço completo: `0xeccbb861c0dda7efd964010085488b69317e4444`
- **Não é uma wallet insider — é o próprio contrato do token** (symbol não resolvido no Dune,
  provavelmente token pequeno/novo sem metadata indexada correctamente)
- As 2327 txs no broker são transferências DESTE token entre wallets, não actividade de uma
  entidade "0xeccbb861" como participante
- TGE: Feb 27, 2026 08:47 UTC (mint para 0x757eba15, depois 0x5c952063 distribui)
- Sellers paralelos Mar 9 07:10-07:50 UTC → broker
- Broker distribui desde Mar 10 04:04 UTC
- Próximo passo (se necessário): identificar o nome real do token via BscScan directo no
  endereço do contrato (Dune não resolve o symbol)
- **TODOS os amounts = NULL** — token usa implementação nao-standard (opaco)
  Amounts invisivel on-chain = ideal para movimentos secretos pre-listing
- Sem simbolo no Dune = token deliberadamente obscuro

### ST — TGE Apr 15, broker Apr 16 (1 dia!) ⭐⭐⭐
- TGE: Apr 15, 2026 10:23 UTC (BSC, contract 0x70be40667385500c5da7f108a022e21b606045dd)
- Apr 16 13:10-13:11 UTC: 10+ sellers paralelos em 18 segundos:
  0xe6451016: 562,744 ST | 0x8d17fbfb: 558,024 ST | 0xb85b0984: 341,324 ST
  + 10 wallets menores (2k-41k ST cada)
- Total broker entry Dia 1: >1.5M ST
- Padrao HYPER (79 dias desde TGE): Apr 15 + 79 = **Jul 3, 2026** 🚨
  (estimativa isolada — não há colisão com QAIT, que já listou 28 Mai, ver correcção Jun 16)
- Activo Jun 12 (57 dias no broker)

---

## Sessões anteriores

- `labbel/sessao_2026-06-11.md` — sessão completa com tabela Supabase e mapa OTC

---

## 26 Ago 2026 — Deploys Railway reparados + cron de holdings pendente de config

- **Builds a falhar desde 19/08** (todos os serviços): `psycopg2-binary==2.9.6` não tem wheel cp313; Railpack resolve Python 3.13.4 e o source build falha. Fix no requirements.txt (`==2.9.10`, commit 13ecf11). Backend voltou a correr código atual (esteve em 17/08).
- **Serviço `holdings-cron` CRIADO** (repo vigia-crypto-deploy, branch main) com todas as variáveis (SUPABASE_URL/SERVICE_ROLE_KEY, HELIUS_API_KEY, ETHERSCAN_API_KEY, TELEGRAM_BOT_TOKEN_SOL/CHAT_ID_SOL). **FALTA (UI do Railway, Settings do serviço — CLI/API dão "Not Authorized" para estes campos):**
  - Root Directory: `backend`
  - Start Command: `python dailyworker/daily_worker_runner.py`
  - Cron Schedule: `0 6 * * *` (diário 06:00 UTC)
  - Redeploy depois (ou push novo dispara).
- **NEEDS_DECISION:** Arkham (trial expirado, 402 desde 13/08) — o `arkham-exchange-scanner` corre diariamente às 08:00 UTC e não escreve nada. Renovar em arkm.com ou remover o cron.
