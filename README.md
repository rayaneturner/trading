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
| **30 %** | **42,4 %** | **38,0 %** | **1,12** | **−43 %** |
| 45 % | 47,6 % | 47,8 % | 1,00 | −57 % |
| 60 % | 44,4 % | 52,3 % | 0,85 | −65 % |

Au-delà de 35 %, le plafond d'exposition et le frein de volatilité font que le risque
augmente sans que le rendement suive. Choisir la ligne dont le max DD est supportable,
pas celle dont le CAGR plaît.

## Résultats réels (BTC + ETH, 2017-01 → 2026-05, nets de 15 bps par côté)

|  | CAGR | vol | Sharpe | max DD | pire mois | Calmar | temps investi | turnover/an |
|---|---|---|---|---|---|---|---|---|
| **Stratégie** | **42,4 %** | 38,0 % | **1,12** | **−43,2 %** | **−23,2 %** | **0,98** | 67,5 % | 3,9× |
| HODL équipondéré | 77,3 % | 74,8 % | 1,03 | −88,0 % | −44,0 % | 0,88 | 100 % | 0,1× |
| HODL BTC | 58,3 % | 68,5 % | 0,85 | −83,8 % | −39,3 % | 0,70 | 100 % | 0,1× |

Par année civile (%) :

| | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026* |
|---|---|---|---|---|---|---|---|---|---|---|
| Stratégie | +161 | **−28** | +71 | +159 | +99 | **−23** | +56 | +38 | +6 | −5 |
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
  Sharpe min 0,74, médiane 1,02, max 1,30. Le résultat est un plateau, pas un pic.
  C'est le seul test qui distingue une règle d'un surajustement.
* **Split 2017–2021 / 2022–2026** : in-sample Sharpe 1,82 (HODL 2,20 — le HODL gagne
  le bull) ; out-of-sample Sharpe 0,50 pour +16,3 % de CAGR contre 0,02 et +0,9 %
  pour le HODL, avec un DD de −39 % contre −68 %.
* **Sensibilité aux coûts** : à 4× les frais (60 bps par côté), Sharpe 1,05. La
  stratégie n'est pas une illusion de frais nuls.
* **Sensibilité au retard d'exécution** : +2 jours de retard, Sharpe 1,12 ; +3 jours,
  1,00. Elle ne dépend pas d'un remplissage rapide.
* **Rebalancement quotidien** : Sharpe 1,15 pour un turnover de 7,0×/an au lieu de
  3,9×. Le gain marginal ne paie pas le risque opérationnel supplémentaire.

## Ce que le backtest ne contient pas, et qui compte

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
python -m pytest tests -q                    # 14 tests : pas de look-ahead, plafonds, coûts
```

Signal du jour depuis un exchange réel (endpoints publics, aucune clé API) :

```bash
python run_live.py --exchange kraken --assets BTC,ETH,SOL
```

Sortie JSON : poids cibles, poids cash, score de tendance et vol par actif, plus
`preflight_problems`. Le script **refuse de produire un signal** si le flux est
périmé (clôtures identiques en fin de série), vieux de plus de 48 h, ou si un actif
n'a pas assez d'historique.

## « Me brancher à un outil pour trader à ta place »

Le point important, et il va à l'encontre de la demande telle que formulée : **ce
n'est pas moi qui dois décider des ordres.** Un LLM dans la boucle de décision
ajoute de la variance non mesurable — je ne suis pas déterministe, je ne suis pas
backtestable, et je n'ai pas de processus persistant. Une règle dont on connaît le
drawdown vaut mieux qu'un jugement dont on ne connaît rien.

L'architecture correcte :

```
cron (1×/jour, 00:10 UTC)  ->  run_live.py  ->  signal déterministe  ->  ordres  ->  exchange
                                     |
                                     +-> out/live.jsonl  (journal auditable)
```

```cron
10 0 * * * cd /chemin/trading && /usr/bin/python3 run_live.py \
    --exchange kraken --assets BTC,ETH,SOL --trade >> out/cron.log 2>&1
```

Trois niveaux, à franchir dans cet ordre et pas plus vite :

| | commande | effet |
|---|---|---|
| 1 | `run_live.py` | signal seul, aucune lecture de compte |
| 2 | `run_live.py --trade` | lit les soldes réels, calcule les ordres, **n'envoie rien** |
| 3 | `TRADING_LIVE=1 run_live.py --trade --live` | envoie les ordres |

Deux interrupteurs indépendants (`--live` **et** `TRADING_LIVE=1`) parce qu'un seul
se déclenche par accident.

Garde-fous codés dans `src/execution.py`, pas dans la stratégie — un bug du signal
peut demander n'importe quoi, l'exécuteur est ce qui empêche que ce soit exécuté :

* notionnel maximum par ordre (`--max-order`, défaut 5 000) ;
* turnover maximum par run = 100 % de l'équity (une rotation complète est 1,0 ; au-delà
  c'est un bug) ; si dépassé, les ventes passent et les achats sont annulés ;
* taille minimale de trade (25 $) et bande morte de 5 % ;
* jamais plus d'achats que de cash disponible ;
* une sortie complète n'est jamais plafonnée ni bloquée ;
* spot uniquement, aucun levier, aucun short, aucun futures ;
* chaque run journalise signal, diagnostics, ordres et reçus dans `out/live.jsonl`.

Clés API : à créer avec les permissions **trade + lecture, sans retrait**, et à passer
par variables d'environnement (`KRAKEN_API_KEY` / `KRAKEN_API_SECRET`). Elles restent
chez vous ; elles ne doivent jamais arriver dans une conversation.

Mon rôle utile, une fois ça branché : surveiller le journal, détecter les dérives
(turnover anormal, ordres rejetés, signal périmé), relancer la validation
périodiquement avec SOL inclus, et vous dire si le régime se dégrade. Pas appuyer sur
le bouton.

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
   Monter seulement après 3 mois sans incident opérationnel.
7. Revue trimestrielle : CAGR, DD réalisé vs backtest, turnover réalisé vs 3,9×/an,
   et slippage réel vs les 15 bps supposés. Si le slippage réel dépasse 40 bps,
   relancez le backtest avec `--cost` au niveau réel avant de continuer.

Critère d'arrêt, à fixer maintenant et pas pendant un drawdown : si le DD dépasse
−55 % (soit 1,3× le pire du backtest), la règle ne se comporte pas comme mesuré —
on arrête et on réexamine, on n'augmente pas la taille.

## Structure

```
src/config.py       paramètres, tous documentés comme décisions de risque
src/datafeed.py     chargement données recherche + flux live ccxt + détection de flux périmé
src/strategy.py     score de tendance, vol réalisée, poids cibles, calendrier et bande morte
src/backtest.py     backtest vectorisé, retard d'exécution et coûts explicites, benchmarks
src/metrics.py      CAGR, Sharpe, Sortino, DD, Calmar, mois perdants
src/walkforward.py  grille, split IS/OOS, sensibilité coûts/retard
src/execution.py    génération d'ordres, garde-fous, exécuteur ccxt (dry-run par défaut)
run_backtest.py / run_validation.py / run_live.py
tests/              14 tests, dont un test explicite d'absence de look-ahead
data/prices_daily.csv   closes quotidiens BTC/ETH (Coin Metrics), 2010 → 2026-05
```

## Avertissement

Ceci n'est pas un conseil en investissement. Les performances passées ne prédisent
rien. Une règle dont le drawdown maximal mesuré est de −43 % produira, un jour, un
drawdown pire que −43 %.
