# Stratégie crypto trend-following — BTC / ETH / SOL

## D'abord : la prémisse de la demande est fausse sur un point

« Une stratégie rentable » n'est pas un objet qu'on écrit. Ce qui existe, c'est une
règle dont l'espérance est positive **sous des hypothèses explicites**, avec une
distribution de résultats dont la queue gauche est connue. Tout ce qui est présenté
comme rentable sans distribution est soit une rétro-optimisation, soit un mensonge.

Deuxième correction : la vraie question n'est pas « quel signal ». Le dimensionnement
et le coût d'exécution déterminent le résultat davantage que le signal. Deux comptes
qui suivent le même signal avec deux tailles de position différentes ont des destins
différents.

Ce dépôt contient donc une règle, son backtest sur données réelles, ses tests de
robustesse, et l'exécuteur — pas une promesse.

## Le raisonnement, depuis les premiers principes

1. BTC/ETH/SOL n'ont pas de flux de trésorerie. Aucune gravité de valorisation ne
   ramène le prix vers une juste valeur. Il n'y a donc rien à « évaluer ».
2. Ce qu'ils ont : des tendances réflexives alimentées par les flux (levier,
   cascades de liquidations, flux ETF, trésoreries d'entreprises) et un clustering
   de volatilité extrême. La structure exploitable est la **persistance**, pas la
   valorisation.
3. Conséquence : ne pas prévoir la direction. Participer tant que la tendance est
   haussière, rester en cash sinon, et dimensionner en inverse de la volatilité
   pour qu'un doublement de la vol ne double pas le risque pris.
4. Chaque paramètre est un coût. Le signal moyenne **trois** votes de tendance lents
   plutôt que d'optimiser un horizon « optimal » : la moyenne de plusieurs horizons
   médiocres est beaucoup plus stable hors échantillon que le meilleur horizon
   in-sample.
5. Long/cash uniquement. Shorter les majors crypto, c'est combattre la dérive
   positive inconditionnelle et payer le funding : autre métier, plus difficile.

## La règle

Par actif, chaque soir à la clôture :

```
score      = moyenne(EMA20 > EMA60,  prix > SMA200,  prix > prix[-90j])   ∈ {0, ⅓, ⅔, 1}
vol        = max(EWMA(vol quotidienne, halflife 20j) × √365,  20 %)
poids brut = score × (30 % / vol),  plafonné à 60 % par actif
poids      = réduit au prorata si l'exposition totale dépasse 100 % (spot, zéro levier)
```

Exécution : rebalancement **hebdomadaire** (lundi), avec une bande morte de 5 points
— une jambe qui dérive de moins de 5 % de l'équity n'est pas tradée. Une sortie
complète n'est jamais bloquée par la bande : réduire le risque doit toujours aboutir.
Le signal de la clôture du jour t est exécuté à la clôture de t+1.

`target_vol` (30 %) est le **seul** cadran de risque à toucher. Mesuré sur 2017–2026 :

| target_vol | CAGR | vol | Sharpe | max DD |
|---|---|---|---|---|
| 10 % | 13,8 % | 13,8 % | 1,00 | −19 % |
| 20 % | 29,2 % | 27,2 % | 1,07 | −33 % |
| **30 %** | **42,6 %** | **38,0 %** | **1,12** | **−43 %** |
| 45 % | 46,8 % | 47,7 % | 0,98 | −57 % |
| 60 % | 44,4 % | 52,2 % | 0,85 | −65 % |

Au-delà de 35 %, le plafond d'exposition et le frein de volatilité font que le risque
augmente sans que le rendement suive. Choisir la ligne dont le max DD est supportable,
pas celle dont le CAGR plaît.

## Résultats réels (BTC + ETH, 2017-01 → 2026-05, nets de 15 bps par côté)

|  | CAGR | vol | Sharpe | max DD | pire mois | Calmar | temps investi | turnover/an |
|---|---|---|---|---|---|---|---|---|
| **Stratégie** | **42,6 %** | 38,0 % | **1,12** | **−43,0 %** | **−23,1 %** | **0,99** | 67,5 % | 3,9× |
| HODL équipondéré | 77,3 % | 74,8 % | 1,03 | −88,0 % | −44,0 % | 0,88 | 100 % | 0,1× |
| HODL BTC | 58,3 % | 68,5 % | 0,85 | −83,8 % | −39,3 % | 0,70 | 100 % | 0,1× |

Par année civile (%) :

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|
| Stratégie | +161 | **−28** | +71 | +158 | +103 | **−23** | +56 | +38 | +5 | −5 |
| HODL éq. | +4209 | −77 | +42 | +399 | +198 | −65 | +123 | +83 | −6 | −21 |

\* 2026 arrêté au 24 mai (fin des données disponibles).

**Lecture honnête de ce tableau.** La stratégie ne bat pas le HODL en rendement
absolu et ne le battra jamais dans une année parabolique : en 2017 elle fait 161 %
contre 4209 %. Ce qu'elle fait, c'est diviser le drawdown maximal par deux
(−43 % vs −88 %) et transformer les deux années de bear market en pertes à deux
chiffres au lieu de −77 % et −65 %. L'écart de Sharpe (1,12 vs 1,03) sur 9,4 ans
est statistiquement indiscernable de zéro — l'erreur-type d'un Sharpe sur 9 ans est
d'environ 0,33. **L'avantage réel est structurel, pas statistique** : il porte sur la
queue gauche, et c'est la queue gauche qui détermine si un compte survit assez
longtemps pour que l'espérance se matérialise, et si son détenteur tient
psychologiquement.

Si l'objectif est le rendement absolu maximal et que vous pouvez tenir −88 % sans
vendre, le HODL équipondéré est la bonne réponse et ce dépôt est inutile. Presque
personne ne tient −88 %.

## Robustesse — `python run_validation.py`

* **Grille de 243 combinaisons** (ema_fast × ema_slow × sma_long × momentum × target_vol) :
  Sharpe min 0,75, médiane 1,02, max 1,30. Le résultat est un plateau, pas un pic.
  C'est le seul test qui distingue une règle d'un surajustement.
* **Split 2017–2021 / 2022–2026** : in-sample Sharpe 1,82 (HODL 2,20 — le HODL gagne
  le bull) ; out-of-sample Sharpe 0,49 pour +16,1 % de CAGR contre 0,02 et +0,9 %
  pour le HODL, avec un DD de −39 % contre −68 %.
* **Sensibilité aux coûts** : à 4× les frais (60 bps par côté), Sharpe 1,05. La
  stratégie n'est pas une illusion de frais nuls.
* **Sensibilité au retard d'exécution** : +2 jours de retard, Sharpe 1,13 ; +3 jours,
  1,02. Elle ne dépend pas d'un remplissage rapide.
* **Rebalancement quotidien** : Sharpe 1,14 pour un turnover de 7,0×/an au lieu de
  3,9×. Le gain marginal ne paie pas le risque opérationnel supplémentaire.

## Ce que le backtest ne contient pas, et qui compte

0. **Le trou se comble avec une commande, depuis une machine qui a accès aux
   exchanges** : `python fetch_history.py --exchange kraken --assets BTC,ETH,SOL`
   reconstruit `data/prices_daily.csv` avec SOL, puis `run_backtest.py` et
   `run_validation.py` revalident tout. Ce qu'il faut n'est pas un outil de replay,
   c'est de l'OHLCV quotidien brut.

1. **SOL n'est pas dans le backtest.** Aucune série de prix SOL n'est accessible
   depuis cet environnement : la policy réseau bloque toutes les API d'exchange
   (Binance, Kraken, Coinbase, CoinGecko…), et le jeu de données Coin Metrics
   accessible ne publie pour SOL qu'une capitalisation estimée — dont les variations
   quotidiennes atteignent +660 %, car elles reflètent des révisions de float, pas
   le prix. L'utiliser aurait produit un chiffre faux. La règle est appliquée à SOL
   en live par transfert : elle est purement price-based et par actif, rien n'y est
   calibré sur BTC/ETH. Mais c'est un choix de prior, pas un résultat validé.
   **Première chose à faire une fois un exchange connecté : `python run_validation.py`
   sur les données live, SOL inclus.** SOL est ~2× plus volatil que BTC, donc le
   dimensionnement inverse-vol lui donnera naturellement un poids ~2× plus petit.
2. **9,4 ans ≈ 2,5 cycles.** C'est très peu. Deux bear markets ne font pas une
   distribution.
3. **Biais de survie du marché lui-même.** BTC et ETH existent encore. La règle ne
   protège pas contre un risque de ruine idiosyncratique (hack d'un L1, échec d'un
   actif), seule la diversification le fait, et trois actifs ne diversifient pas
   grand-chose : BTC/ETH/SOL sont corrélés à 0,7–0,9 en régime de stress. En pratique
   la vraie diversification ici vient du cash, pas du nombre d'actifs.
4. **Risque de contrepartie non modélisé.** Le backtest suppose que l'exchange rend
   les fonds. FTX a démontré le contraire. Ne laissez sur la plateforme que ce qui
   est nécessaire aux ordres.
5. **Le régime peut mourir.** Si la crypto devient un actif macro mature avec une
   vol de 25 % et pas de tendance longue, le trend-following cesse de payer et vous
   payerez 3,9×/an de frottement pour rien. Le signal d'alarme à surveiller : un
   Calmar glissant sur 2 ans durablement sous 0,3.

## Utilisation

```bash
pip install -r requirements.txt

python run_backtest.py                       # performance vs HODL sur les données de recherche
python run_backtest.py --cost 0.003          # avec des frais doublés
python run_validation.py                     # grille, split IS/OOS, sensibilités
python -m pytest tests -q                    # 25 tests : look-ahead, plafonds, coûts, enveloppe
```

Signal du jour depuis un exchange réel (endpoints publics, aucune clé API) :

```bash
python run_live.py --exchange kraken --assets BTC,ETH,SOL
```

Sortie JSON : poids cibles, poids cash, score de tendance et vol par actif, plus
`preflight_problems`. Le script **refuse de produire un signal** si le flux est
périmé (clôtures identiques en fin de série), vieux de plus de 48 h, ou si un actif
n'a pas assez d'historique.

## Brancher un agent LLM dessus

C'est faisable, c'est codé ici, et il faut d'abord être clair sur ce qu'on ne peut
pas faire : **un agent LLM n'est pas backtestable.** Deux raisons dures.

1. **Non-déterminisme.** Deux appels sur le même état donnent deux décisions. Un
   backtest sur un run est un échantillon de taille 1.
2. **Contamination totale.** Le modèle a été entraîné sur des données qui incluent
   l'historique des prix jusqu'à son cutoff (mai 2026 pour `claude-opus-5-5`). Lui
   faire « rejouer » mars 2020 ou novembre 2021, c'est demander à quelqu'un qui
   connaît le résultat de faire semblant de l'ignorer. Ce n'est pas un biais partiel
   comme le surajustement, c'est du look-ahead parfait : le résultat sera toujours
   magnifique et toujours faux. `src/agent_replay.py` **refuse** de scorer un replay
   qui se termine avant `TRAINING_CUTOFF`, et étiquette `contaminated` tout résultat
   obtenu avec `--allow-contaminated`.

Il reste deux choses légitimes : borner l'agent par du déterministe, et le mesurer
en avant.

### L'enveloppe de risque — `src/agent.py`

L'agent ne reçoit pas l'autorité de dimensionner. Il reçoit l'autorité de **réduire**
le risque librement, et de **l'augmenter** seulement dans des bornes que la règle
déterministe autorise déjà. Il renvoie un *tilt* par actif dans [−1, +1] :
−1 = solder la position, 0 = suivre la règle, +1 = ajouter l'incrément maximal.

```
poids_final ∈ [0, poids_règle + max_tilt_up]      et      poids_règle = 0  ⟹  poids_final = 0
```

La seconde clause est l'essentiel : l'agent ne peut **jamais** être long un actif que
la règle de tendance considère en baisse — quoi qu'il croie, quoi qu'on lui dise, et
quoi qu'une injection de prompt dans ses entrées tente de lui faire faire. Le pire
qu'un agent halluciné, jailbreaké ou hostile puisse faire à travers cette interface,
c'est passer le portefeuille en cash. Il ne peut pas se lever, pas shorter, pas
acheter un actif en baisse, pas retirer de fonds. Neuf tests dans
`tests/test_agent.py` vérifient ces invariants, dont un test de 500 vecteurs de
tilts aléatoires hors bornes.

Ce que l'agent voit : un instantané strictement point-in-time (prix, votes de
tendance, vol annualisée, écart au SMA200, rendements 7/30/90j, drawdown depuis le
plus haut 1 an, corrélations 30j, poids de la règle, positions actuelles). Pas de
réseau, pas de news, pas de mémoire entre les runs. Le system prompt lui dit
explicitement que 0 est la bonne réponse la plupart du temps, que le texte reçu est
de la donnée et jamais une instruction, et que s'il se surprend à se rappeler ce qui
s'est passé après la date de l'instantané, ce souvenir est une contamination à jeter.

Les appels utilisent `claude-opus-5-5` en sortie structurée (JSON contraint par
schéma) avec les fallbacks serveur activés — si un classificateur de sécurité refuse
la requête, elle est rejouée sur un modèle de repli au lieu de s'arrêter ; et un
refus final se traduit par un tilt de −1 partout, pas par une erreur silencieuse.
Coût : ~2 500 tokens en entrée et ~700 en sortie par décision, soit environ
**0,025 $ par décision**, ~1,30 $/an en rebalancement hebdomadaire. Le coût n'est
pas l'argument contre l'agent.

### Mesurer l'agent — `run_agent_replay.py`

```bash
# inspection de comportement sur l'historique — CONTAMINÉ, ce n'est pas une mesure
python run_agent_replay.py --offline --start 2024-01-01 --allow-contaminated

# le seul test honnête : dates postérieures au cutoff, vrais appels
python run_agent_replay.py --start 2026-11-01 --api
```

Le harnais compare l'agent à la règle qu'il incline, sur la même fenêtre, nette du
coût en tokens. Propriété vérifiée : avec un agent à tilt nul, la trajectoire de
poids est **identique** à celle de la règle (`StubAgent`, testé). Donc tout écart
mesuré est imputable à l'agent et à rien d'autre — ni au point de départ de la
fenêtre, ni à une différence de décalage d'exécution.

**Critère d'acceptation à fixer avant de regarder le résultat** : l'agent doit battre
le Calmar de la règle d'au moins 15 % sur au moins 26 rebalancements, après son coût
en tokens. En dessous, la machinerie ne se paie pas : on fait tourner la règle
déterministe et on garde l'argent. Mon estimation, à énoncer maintenant pour qu'elle
soit falsifiable : **probabilité faible, 25-35 %, que l'agent passe ce critère.** Ce
qui me ferait changer d'avis : un écart positif persistant sur 26+ décisions
concentré sur les retournements (là où une règle à moyenne de trois horizons est
structurellement en retard), pas étalé uniformément.

### « Te mettre dans l'outil » — `mcp_server.py`

Serveur MCP, cinq outils : `get_signal`, `get_portfolio`, `plan_rebalance`,
`execute_rebalance`, `get_limits`. Configuration côté client :

```json
{"mcpServers": {"trading": {"command": "python",
  "args": ["/chemin/trading/mcp_server.py"],
  "env": {"TRADING_EXCHANGE": "kraken", "TRADING_ASSETS": "BTC,ETH,SOL"}}}}
```

Décision de conception qui compte : **ce serveur n'accepte pas de poids cibles.** Un
client ne peut proposer que des tilts ; le serveur calcule les poids lui-même et les
borne. Un agent branché par MCP hérite donc de l'enveloppe par construction, sans
qu'on ait à lui faire confiance.

### Les trois niveaux d'exécution

| | commande | effet |
|---|---|---|
| 1 | `run_live.py` / `run_agent.py` | signal seul, aucune lecture de compte |
| 2 | `... --trade` | lit les soldes réels, calcule les ordres, **n'envoie rien** |
| 3 | `TRADING_LIVE=1 ... --trade --live` | envoie les ordres |

Deux interrupteurs indépendants (`--live` **et** `TRADING_LIVE=1`) parce qu'un seul se
déclenche par accident. Un appel d'outil ne peut pas basculer `TRADING_LIVE` : c'est
l'environnement du processus, pas un paramètre.

En cron, une décision par jour à 00:10 UTC :

```cron
10 0 * * * cd /chemin/trading && /usr/bin/python3 run_agent.py \
    --exchange kraken --assets BTC,ETH,SOL --trade >> out/cron.log 2>&1
```

Garde-fous codés dans `src/execution.py`, pas dans la stratégie — un bug du signal ou
une hallucination de l'agent peut demander n'importe quoi, l'exécuteur est ce qui
empêche que ce soit exécuté :

* notionnel maximum par ordre (`--max-order`, défaut 5 000) ;
* turnover maximum par run = 100 % de l'équity (une rotation complète vaut 1,0 ;
  au-delà c'est un bug) ; si dépassé, les ventes passent et les achats sont annulés ;
* taille minimale de trade (25 $) et bande morte de 5 % ;
* jamais plus d'achats que de cash disponible ;
* une sortie complète n'est jamais plafonnée ni bloquée ;
* refus de trader sur un flux de prix périmé ;
* spot uniquement, aucun levier, aucun short, aucun futures ;
* chaque run journalise instantané, décision, ordres et reçus dans `out/*.jsonl`.

Clés API : permissions **trade + lecture, sans retrait**, passées par variables
d'environnement (`KRAKEN_API_KEY` / `KRAKEN_API_SECRET`, `ANTHROPIC_API_KEY`). Elles
restent chez toi et ne doivent jamais arriver dans une conversation.

### Ce que l'architecture ne règle pas

L'enveloppe borne les dégâts, elle ne crée pas de compétence. Un agent qui tilte au
hasard dans [−1, 0] va simplement sous-performer la règle en restant trop souvent en
cash, et ça ne se verra qu'après plusieurs mois de mesure. C'est précisément pour ça
que le critère d'acceptation se fixe avant, et que le niveau 3 attend la mesure.

## Prochaines étapes concrètes, dans l'ordre

1. `python -m pytest tests -q` puis `python run_backtest.py` — vérifier que les
   chiffres ci-dessus se reproduisent chez vous.
2. Choisir `target_vol` dans le tableau des cadrans. Critère : le max DD de la ligne
   doit être un chiffre que vous pouvez voir sur votre compte sans intervenir.
   Si vous hésitez, prenez la ligne du dessous.
3. `python run_live.py --exchange kraken --assets BTC,ETH,SOL` pendant **au moins
   4 semaines** sans trader. But : vérifier que le flux est fiable et observer la
   fréquence réelle des changements de poids.
4. Pendant ces 4 semaines : `python run_validation.py` sur les données live avec SOL.
   Critère d'acceptation : Sharpe médian de la grille > 0,8 et Calmar OOS > 0,3 avec
   SOL inclus. Si SOL fait chuter la médiane sous 0,8, retirez SOL de l'univers.
5. Passer en niveau 2 (`--trade` sans `--live`) une semaine, et comparer les ordres
   proposés à ce que vous auriez fait à la main.
6. Niveau 3 avec 5 à 10 % du capital cible et `--max-order` à 2 % de l'équity.
   Monter seulement après 3 mois sans incident opérationnel. **La règle
   déterministe seule** (`run_live.py`) à ce stade, pas l'agent.
7. L'agent LLM seulement après ça, et seulement en mesure : `run_agent.py --offline`
   d'abord (il suit la règle, c'est la baseline à battre), puis `--api` sur dates
   postérieures au cutoff, pendant au moins 26 rebalancements, sans trader. Comparer
   au critère d'acceptation ci-dessus. S'il ne passe pas, garder la règle : c'est le
   résultat le plus probable et ce n'est pas un échec, c'est une mesure.
8. Revue trimestrielle : CAGR, DD réalisé vs backtest, turnover réalisé vs 3,9×/an,
   et slippage réel vs les 15 bps supposés. Si le slippage réel dépasse 40 bps,
   relancez le backtest avec `--cost` au niveau réel avant de continuer.

Critère d'arrêt, à fixer maintenant et pas pendant un drawdown : si le DD dépasse
−55 % (soit 1,3× le pire du backtest), la règle ne se comporte pas comme mesuré —
on arrête et on réexamine, on n'augmente pas la taille.

## Structure

```
src/config.py       paramètres, tous documentés comme décisions de risque
src/datafeed.py     données recherche + flux live ccxt (paginé) + détection de flux périmé
src/strategy.py     score de tendance, vol réalisée, poids cibles, calendrier et bande morte
src/backtest.py     backtest vectorisé, retard d'exécution et coûts explicites, benchmarks
src/metrics.py      CAGR, Sharpe, Sortino, DD, Calmar, mois perdants
src/walkforward.py  grille, split IS/OOS, sensibilité coûts/retard
src/execution.py    génération d'ordres, garde-fous, exécuteur ccxt (dry-run par défaut)
src/agent.py        instantané point-in-time, appel LLM en sortie structurée, enveloppe de risque
src/agent_replay.py harnais de mesure de l'agent, avec refus des fenêtres contaminées
mcp_server.py       serveur MCP : lecture d'état + tilts bornés, jamais de poids directs
fetch_history.py    reconstruit le CSV de recherche depuis un exchange (à lancer chez toi)
run_backtest.py / run_validation.py / run_live.py / run_agent.py / run_agent_replay.py
tests/              25 tests, dont l'absence de look-ahead et les invariants de l'enveloppe
data/prices_daily.csv   closes quotidiens BTC/ETH (Coin Metrics), 2010 → 2026-05
```

## Avertissement

Ceci n'est pas un conseil en investissement. Les performances passées ne prédisent
rien. Une règle dont le drawdown maximal mesuré est de −43 % produira, un jour, un
drawdown pire que −43 %.
