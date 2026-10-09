Tu vas travailler sur ma stratégie de trading PIFF sur le NAS100, via mon compte
MoonX (connecteur MCP déjà configuré). Lis tout avant de commencer : le code
existe déjà, et les erreurs listées plus bas ont déjà coûté une demi-journée.

## Mon compte et la place de marché

- MoonX, wallet forex/CFD, solde ~21 USD. Instrument : NAS100 (CFD sur indice).
- **Je risque 2 USD par trade**, en absolu. Pas un pourcentage.
- Paramètres MESURÉS sur des exécutions réelles, ne les recalcule pas depuis
  les métadonnées de l'API (je m'y suis fait piéger, voir erreur n°1) :
  - **3,50 USD par point par LOT** → 0,01 lot = **0,035 USD/point**
    (vérifié : 0,001 lot sur 11,4 points = +0,0399 USD ; 0,01 lot sur 0,95 point
    = +0,03325 USD)
  - **lot minimum 0,000001** (vérifié, un ordre de cette taille a été rempli)
  - **frais 0,010 % par côté** sur les indices, prélevés à l'ouverture ET à la
    fermeture
  - levier 500x appliqué d'office par la plateforme
  - dimensionnement : `lots = risque_USD / (stop_points × 3,5)`, arrondi au
    pas INFÉRIEUR
- Pose TOUJOURS un stop loss sur chaque position.

## La stratégie PIFF, telle que je la trade

**Biais directionnel** (optionnel) : la tendance sur M15, M30 ou H1. Attention,
une EMA 20/50 sur M15 retarde beaucoup — elle m'a bloqué des shorts pendant une
chute de 190 points. La stratégie fonctionne parfois sans suivre le biais.

**Structure : je lis les cassures de tendance en M5.** Pas en M15.

**La séquence, dans cet ordre :**

1. **Balayage de liquidité** — une bougie M5 mèche au-delà d'un extrême de
   structure (plus-haut ou plus-bas) PUIS clôture de l'autre côté. Un niveau
   simplement traversé ne compte pas : il faut mèche + reprise. C'est la chasse
   aux stops.
2. **Cassure de structure M5** — une clôture M5 au-delà du swing opposé.
3. **FVG en M1** — le déséquilibre à 3 bougies laissé par la jambe de
   déplacement. Il se situe vers la première mèche cassée, à l'origine du
   mouvement. Le FVG peut aussi naître APRÈS la cassure, dans la jambe de
   continuation.
4. **Retour dans le FVG + confirmation.** En général il y a un **fake** (le prix
   poke la zone une première fois) PUIS un retest avec une bougie confirmante :
   englobante, ou marteau / bougie de rejet. Parfois j'entre à la première
   bougie confirmante dans la zone, sans attendre le fake.
5. **Entrée**, de deux façons selon le cas :
   - **limite** au bord du FVG, quand c'est le premier contact → le stop
     s'appuie sur le niveau balayé (plus large)
   - **stop** sur la cassure de l'extrême de la bougie confirmante, quand il y a
     eu un retest → le stop s'appuie sur cette bougie (plus serré)
6. **Stop loss** : juste au-delà de la dernière bougie M1 (la confirmante), avec
   un petit buffer.
7. **Take profit** : au niveau de la dernière mèche haute/basse créée par le
   mouvement précédent — celui qui a cassé le mouvement d'avant encore. C'est le
   pool de liquidité **AU-DELÀ** du niveau de cassure, pas le niveau de cassure.

**Mes trades loggés en backtest FX Replay**, pour calibration :
stops de 16,6 / 21,8 / 29,3 / 44,8 points. R:R typiquement 4:1.
Taux de réussite 59,23 % sur 61 trades. Un gagnant réel : entrée 30 874,95,
SL 30 923 (48 pts), TP 30 581 (294 pts) — donc je prends aussi des objectifs
larges sur des niveaux qui ne sont pas des swings de la séance.

## Les 5 erreurs déjà commises — ne les refais pas

1. **La valeur du point.** Une position NAS100 renvoie `contractSize: 3.5`,
   `pipSize: 1`, `pipValue: 3.5`. **`pipValue` est la valeur du point pour UN
   LOT**, pas pour la position. L'avoir lu comme la valeur de la position a
   surestimé le risque d'un facteur 100 et produit la conclusion fausse qu'il
   fallait ~900 USD de capital. Utilise les constantes mesurées ci-dessus.
2. **Ne lis jamais un signal sur une bougie non clôturée.** Une cassure de
   structure est une CLÔTURE au-delà d'un niveau. En direct, la bougie M5
   estampillée 14:30 affichait une clôture de 30 863,3 à 14:30 et 30 851,8 à
   14:32 — au-dessus puis en dessous du seuil. Le signal repeint. Écarte
   toujours la dernière bougie tant que la période n'est pas complète.
3. **Un FVG poké n'est pas invalidé** — ce poke EST le fake, et le trade est le
   RETOUR. Seule une **clôture** au-delà du bord opposé tue la zone.
4. **Le TP n'est jamais le niveau dont la cassure définit le setup.** La
   structure ne casse que quand le prix clôture au-delà de ce niveau, donc viser
   ce niveau = objectif déjà atteint au moment où le setup devient valide. Ça a
   produit un R:R de 0,66 sur un setup qui valait 4,46. Vise le pool suivant.
   Et quand la cassure prend l'extrême de la séance, il n'y a plus de pool :
   utilise un multiple du stop (4R) plutôt que de refuser le trade.
5. **Cherche le FVG du balayage jusqu'à MAINTENANT**, pas seulement jusqu'à la
   cassure. Le gap qui se fait retester est souvent creusé par le déplacement
   qui SUIT la cassure.

Deux réglages qui en découlent : **swing fractal k=1** sur la structure (avec
k=2 un sommet fait à 14:05 n'est un swing qu'à 14:20, trop tard), et **structure
en M5**.

## Le code existe

GitHub : `rayaneturner/trading`, branche `claude/crypto-trading-strategy-3ljx1n`

- `src/piff.py` — le moteur. Dit **où** il refuse, étage par étage.
- `src/piff_live.py` — pont depuis les bougies MoonX, avec contrôle
  d'intégrité : MoonX m'a renvoyé 439 bougies sur 500 mal agrégées sur une
  requête 15m (espacées de 60 s au lieu de 900 s). Toute série est vérifiée
  contre l'espacement que son timeframe implique.
- `src/piff_moonx.py` — dimensionnement, constantes calibrées sur fills réels.
- `src/piff_watch.py` — la boucle, avec stop journalier 5 %, une position à la
  fois, annulation des ordres orphelins, plafond de risque.
- `src/moonx_client.py` — client MCP pour tourner hors session (non testé : le
  réseau du conteneur refusait api.moon-x.io).
- `run_piff.py`, `run_watch.py` — les exécutables. **Mode lecture seule par
  défaut**, `--live` est un choix séparé.
- **141 tests passent.** `python -m pytest -q`

## Ce qui N'EST PAS établi

**Le moteur n'a jamais été backtesté.** Les tests prouvent qu'il applique la
règle, pas qu'elle gagne. `get_candles` de MoonX plafonne à 500 bougies et
n'accepte aucune date de début, donc l'historique nécessaire est inaccessible
depuis le code. Les 59,23 % viennent de mon backtest FX Replay, pas d'une
mesure reproductible.

Garde en tête l'identité qui gouverne tout :
`seuil_de_rentabilité = (1 + frais/distance_du_stop) / (1 + R:R)`.
Les frais en R ne dépendent **pas** du R:R, seulement de la largeur du stop.
Sur NAS100 à 0,010 %/côté, un stop de 25 pts coûte 0,24 R — confortable.

## Ce que j'attends de toi

1. Vérifie que MoonX répond (`get_account_overview`). S'il demande une
   réautorisation, dis-le-moi.
2. Quand je dis **« check »** : récupère NAS100 en 1m (limit 500) et 15m
   (limit 500), évalue avec le moteur en structure M5, dans les deux modes
   (immédiat et ordre en attente), dimensionne à 2 USD, et dis-moi le résultat.
   **Si c'est FLAT, dis-le franchement avec la raison précise** — un refus est
   un résultat valide, ne force jamais un signal.
3. Si un setup valide apparaît, place-le : ordre au marché ou ordre limite selon
   le mode, avec SL et TP attachés.
4. Si je prends des trades manuellement, ne les gère pas sauf si je le demande.
5. Ne me dis jamais qu'une stratégie est rentable sans l'avoir mesurée. Donne
   les chiffres, l'erreur type, et le seuil à battre.

Commence par vérifier l'état du compte et me dire si le moteur voit un setup
maintenant.
