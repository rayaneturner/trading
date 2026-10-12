# Le BPR mesuré

Code : `src/bpr.py`, étude : `run_bpr.py`, tests : `tests/test_bpr.py`.
Données : BTC/ETH/SOL/BNB 1h, BTC 15m et 4h, 2020 → juin 2026.
Un BPR tous les ~22 bougies, 2 000 à 10 600 zones par série : l'échantillon
n'est pas le problème.

## La règle testée

Un FVG haussier et un FVG baissier formés à moins de 20 bougies l'un de
l'autre, dont le chevauchement dépasse 0,05 ATR14. La zone est leur
intersection, le FVG le plus récent donne le sens. Entrée au retest, à la
clôture de la bougie qui déclenche. Stop au bord opposé de la zone + 0,25 ATR,
objectif 2R. Une position à la fois, 100 bougies maximum.

Une bougie qui touche stop et objectif est comptée perdante : la donnée ne dit
pas lequel est arrivé en premier. Aucune valeur n'est lue avant sa clôture.

## Ce que ça donne

Taux de réussite contre le seuil d'équilibre (33,33 % à 2R), frais nuls :

| Série | n | wr | E |
|---|---|---|---|
| BTC 1h | 1 589 | 30,1 % | −0,095 R |
| ETH 1h | 1 772 | 29,9 % | −0,101 R |
| SOL 1h | 1 672 | 30,2 % | −0,095 R |
| BNB 1h | 1 908 | 32,3 % | −0,032 R |
| BTC 15m | 8 221 | 30,9 % | −0,074 R |
| BTC 4h | 443 | 30,0 % | −0,099 R |

Six séries, six résultats négatifs avant frais. Le déclencheur « rejet
confirmé » (la zone est touchée, puis le prix referme en dehors) rattrape
l'essentiel de l'écart et ramène le taux sur le seuil : 32,7 % BTC 1h,
33,1 % BTC 15m, 34,5 % SOL 1h. Il annule la perte, il ne crée pas de gain.

## Le biais ne porte aucune information

Même zones, direction inversée : −0,15 R BTC 1h, −0,16 R ETH, −0,23 R BNB.
Les deux sens perdent, donc la convention « le FVG le plus récent donne le
sens » ne sépare rien. Ce qui coûte, c'est l'entrée au contact d'un niveau que
le prix est en train de traverser, pas le choix du côté.

## Rien ne survit à la recherche

72 variantes (déclencheur × objectif × RR, hors échantillon) : meilleur
t = +1,27. La barre de Bonferroni pour 72 essais est à t ≈ 3,3. Les quelques
variantes à E positif sont celles qui visent « la liquidité opposée » avec un
R:R affiché de 25 à 60 — artefact de stops microscopiques, taux de réussite
14 %, t sous 1,3.

Le meilleur candidat (rejet confirmé, zone > 0,25 ATR, 2R) testé dedans/dehors :
SOL passe de +0,28 R en in-sample à −0,07 R dehors, ETH de +0,10 R à −0,12 R,
BNB de +0,04 R à +0,14 R. Les signes changent d'une moitié d'historique à
l'autre. C'est du bruit.

## Les frais décident

La largeur médiane d'un BPR est de 0,17 ATR. Stop au bord : distance médiane
0,37 % du prix sur BTC 1h, quartile bas 0,19 %. À 4 bps par côté, l'aller-retour
coûte 0,22 R médian et la moyenne explose sur les zones les plus fines. Net de
frais, la meilleure configuration hors échantillon est à −0,11 R (BTC 1h),
−0,30 R (BTC 15m), +0,01 R (BNB 1h, n = 240).

Filtrer sur des zones plus larges réduit la facture sans créer d'edge :
chevauchement > 0,50 ATR donne +0,06 R sur ETH 1h pour n = 149 — t = +0,51.

## Conclusion

Le BPR seul, comme signal d'entrée mécanique, n'a pas d'edge sur ces six
séries. Il localise correctement des zones de réaction — le taux de réussite
colle au seuil d'équilibre, ce qui veut dire que le prix réagit autant qu'il
traverse — mais il ne dit pas dans quel sens, et le coût d'exécution sur des
stops aussi serrés fait le reste.

Ce qui reste à tester, dans l'ordre de l'espérance de gain :
1. Le BPR comme **filtre de zone** et non comme signal : exiger une prise de
   liquidité préalable (`src/ict_sweep.py` a déjà le détecteur de sweep), le
   BPR ne servant qu'à placer l'entrée et le stop.
2. Le contexte de séance : BPR formés en killzone de Londres ou de New York
   contre le reste.
3. Le stop : sortir du bord de zone, qui est trop serré pour les frais, et
   tester un stop ATR plus large avec le même objectif structurel.
