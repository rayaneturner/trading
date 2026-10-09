# L'Art du trading — Thami Kabbaj

Notes de lecture. 561 pages, lu depuis le Drive de Rayane. Ce fichier est
ma synthèse, pas le texte du livre : le PDF reste sur son Drive, il n'est
pas copié dans ce dépôt.

Ce que j'ai lu intégralement : chapitre 13 (dimension stratégique),
chapitre 14 (money management), l'introduction, le chapitre 1 et le
chapitre 2 (finance comportementale). Lecture ciblée ailleurs par
recherche. Les chapitres 5 à 12 (analyse technique, bougies,
indicateurs) n'ont pas été lus en entier — ils décrivent des outils déjà
implémentés dans `src/`.

## Le livre en une ligne

Universitaire, pas commercial. Cite Kahneman, Tversky, Thaler, Thorp,
Balsara, Bailey, Livermore, Seykota, Sun Tzu. Chiffres et formules
vérifiables, contrairement aux PDF HowToTrade. Le chapitre 14 est le seul
de tout le corpus reçu qui parle de dimensionnement de position.

## Les trois passages qui tranchent sur ce projet

### 1. Il nous donne raison sur les frais, explicitement

> « La stratégie de domination globale par les coûts profite
> essentiellement aux traders institutionnels qui ont des frais de
> transaction extrêmement faibles et peuvent profiter de petits
> mouvements de marché. »

Kabbaj classe la capture de petits mouvements comme un avantage
structurel de coût réservé aux institutionnels. C'est exactement ce que
mesurent `research/hourly_cadence_scan.py` et
`research/target_feasibility.py` : à 0.070 %/côté, 3 trades par jour
coûtent 153 % du capital par an. Le projet de scalping à haute fréquence
sur MoonX est démenti par le livre lui-même.

Thorp, qu'il cite : les conditions ne sont favorables que 10 % du temps.
Donc peu de trades, pas beaucoup.

### 2. Son argument central sur le Risk/Reward contient le trou qu'on a mesuré

> « si pour chaque investissement, le gain potentiel est supérieur à 3
> fois la perte assumée, même en se trompant dans deux cas sur trois, le
> trader réalisera une performance positive (hors frais de
> transactions). »

L'arithmétique est juste : à 3:1, le seuil est 25 %, donc 33 % donne
+0.33 R. Deux objections, et il écrit la seconde lui-même.

**a.** Sur une marche aléatoire, P(toucher +3R avant −1R) = 1/4 = 25 %,
exactement le seuil. Gagner 33 % à 3:1 suppose 8 points au-dessus du
hasard. C'est tout l'edge, supposé et non démontré. Mesuré sur 11 129
trades H4-break : 32.1 % à 2:1 contre 33.3 % aléatoire — en dessous.

**b.** « hors frais de transactions », entre parenthèses, dans sa propre
phrase. C'est la variable qui a décidé chacun de nos tests.

### 3. Sa formule de Kelly s'annule si on relie W et R

Le livre donne `K% = W − (1−W)/R` et traite W et R comme indépendants :
montez le ratio, la taille optimale grandit. Mais sur une marche
aléatoire W = 1/(1+R), et en substituant :

    K = 1/(1+R) − (R/(1+R))/R = 1/(1+R) − 1/(1+R) = 0

**Exactement zéro, à tous les ratios.** Vérifié dans
`research/kelly_vs_random_walk.py`. Le R:R seul n'achète rien. Tout
Kelly positif vient des points de taux de réussite au-dessus du hasard,
et ces points-là se paient en frais.

Table produite par le script (edge réel de +8 points) :

| R:R | W aléatoire | Kelly | W +8 pts | Kelly | Kelly après 0.48 R de frais |
|----:|------------:|------:|---------:|------:|----------------------------:|
|   1 |       50.0% |  0.0% |    58.0% | +16.0%|                      −22.8% |
|   2 |       33.3% |  0.0% |    41.3% | +12.0%|                       +2.7% |
|   3 |       25.0% |  0.0% |    33.3% | +11.1%|                       +6.9% |
|   5 |       16.7% |  0.0% |    24.7% |  +9.6%|                       +8.0% |

Lecture : à 1:1 avec les frais crypto, Kelly est négatif même avec un
edge réel de 8 points — le système est à ne pas jouer. Le ratio élevé ne
crée pas d'edge, il **dilue les frais**, et c'est la seule raison de le
préférer.

## Ce que je retiens d'utile et d'applicable

- **R:R ≥ 2 minimum, ≥ 3 préféré.** Pas parce que ça crée un edge, mais
  parce que ça divise le poids des frais. Même conclusion, raison
  différente de la sienne.
- **Risque fixe en % du capital**, pas en montant fixe. Déjà appliqué
  dans `src/piff_moonx.py`.
- **Kelly fractionnaire.** Il critique Kelly plein avec un exemple juste :
  un day trader à 70 % / R=1 obtient 40 % par Kelly, et trois pertes
  consécutives le ruinent. Sa règle : dimensionner pour survivre à 20
  pertes d'affilée. Cohérent avec le demi-Kelly de
  `research/target_feasibility.py`.
- **Risque de ruine, Balsara** : `P(ruine) = (q/p)^k`, k = unités de
  capital. À 55 % et R=1 sur 10 unités : 13.4 %. À 50 % et R=1 : ruine
  quasi certaine quel que soit k — « son système ne lui procure aucun
  avantage ».
- **Stop déplaçable dans un seul sens**, jamais contre la position.
- **Stop qui tient compte de la volatilité**, pas seulement du niveau
  structurel. Converge avec ce qu'on a mesuré sur `ict_sweep` : le stop
  sous la liquidité balayée (1.59 %) plutôt que sous la bougie (0.147 %)
  fait passer les frais de 0.95 R à 0.088 R.
- **Arrêt de la journée à −5/−10 %.** `WatchConfig.daily_loss_stop` est
  à 5 %. Conforme.

## Ce que je ne retiens pas

- **Vagues d'Elliott et ratios de Fibonacci** (section Risk/Reward du
  ch. 14). Aucun des tests de ce dépôt n'a trouvé de contenu
  informationnel dans un niveau de retracement. Les exemples du livre
  sont rétrospectifs, sur un graphique choisi après coup, sans
  distribution ni nombre de trades.
- **« Le payoff ratio a plus de poids que la probabilité de succès. »**
  Vrai pour le risque de ruine, faux comme conseil : les deux sont liés
  par la barrière, on ne monte pas l'un sans baisser l'autre.
- Le chapitre 13 (Sun Tzu) est de la métaphore, pas une règle testable.

## Conséquence pour la suite

Rien ici ne change le diagnostic : l'obstacle n'est pas la méthode
d'entrée, c'est le couple frais/largeur de stop, et la cible de
5–10 %/mois à 3 trades/jour. Le livre appuie ce diagnostic sur ses deux
passages les plus sérieux et le contredit sur un seul, dont la faille est
mesurée ici même.
