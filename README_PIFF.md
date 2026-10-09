# PIFF — lancer le bot

## Ce que c'est

Le moteur mécanise la stratégie PIFF sur NAS100 : balayage de liquidité →
cassure de structure (M5) → retour sur un FVG M1 → confirmation → entrée, avec
stop derrière la structure et objectif sur le pool de liquidité suivant.

Trois fichiers font le travail, et ils sont séparés exprès :

| Fichier | Rôle |
|---|---|
| `src/piff.py` | la règle. Lit les bougies, décide, et dit **où** elle a refusé |
| `src/piff_moonx.py` | le dimensionnement, calibré sur des exécutions réelles |
| `src/piff_live.py` | le pont depuis les bougies MoonX, avec garde d'intégrité |
| `src/moonx_client.py` | parle à MoonX (MCP sur HTTP) |
| `src/piff_watch.py` | la boucle, et tous les garde-fous |
| `run_watch.py` | le programme à lancer |

## Installer

```bash
git clone https://github.com/rayaneturner/trading.git
cd trading
pip install pandas numpy requests pytest
python -m pytest -q          # doit afficher 113 passed
```

## Lancer

Le jeton ne se met **jamais** sur la ligne de commande : il resterait dans
l'historique du shell.

```bash
export MOONX_MCP_TOKEN=mcp_xxxxx
python run_watch.py                 # lecture seule : décide, n'envoie rien
python run_watch.py --live          # envoie les ordres
python run_watch.py --once          # une seule passe, puis sort
```

Options utiles : `--risk 2` (USD par trade), `--min-rr 2`, `--poll 60`
(secondes entre deux passes), `--daily-stop 0.05`, `--pair NAS100`.

Tout est écrit dans `piff.log`. Les passes identiques sont regroupées, donc une
ligne par changement d'état et pas une par minute.

## Sur un serveur, pour que ça tourne sans toi

```bash
# dans /etc/systemd/system/piff.service
[Unit]
Description=PIFF
After=network.target

[Service]
WorkingDirectory=/root/trading
Environment=MOONX_MCP_TOKEN=mcp_xxxxx
ExecStart=/usr/bin/python3 run_watch.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now piff
journalctl -fu piff          # suivre en direct
```

`Restart=always` relance le bot s'il plante ou si le serveur redémarre.

## Les garde-fous, et pourquoi ils existent

- **lecture seule par défaut.** `--live` est un choix séparé.
- **stop journalier à 5 %.** Une fois atteint, plus rien jusqu'au lendemain, et
  une remontée du solde ne rouvre pas la journée.
- **une position et un ordre à la fois.** Pas d'empilement.
- **annulation des ordres orphelins.** Un ordre dont le setup a disparu est un
  trade que plus personne n'a décidé.
- **plafond de risque.** Un trade qui dépasse la fraction permise est refusé,
  avec la raison.
- **flux figé = marché fermé.** Pas de décision sur des prix qui ne bougent plus.
- **bougies vérifiées.** MoonX a renvoyé 439 bougies sur 500 mal agrégées sur
  une requête 15m ; les séries sont contrôlées contre l'espacement que leur
  propre timeframe implique.
- **pas de signal sur une bougie non close.** Une cassure lue sur une bougie en
  formation disparaît : vu en direct, 30 863 à 14:30 puis 30 851 à 14:32.

## Ce qui n'est pas établi

Les 113 tests montrent que le moteur applique la règle. **Ils ne montrent pas
que la règle gagne de l'argent.** Il n'existe aucune mesure de performance :
MoonX ne sert que 500 bougies par requête et sans date de début, donc l'historique
nécessaire à un backtest n'est pas accessible depuis ce code.

Cinq défauts ont été trouvés dans ce moteur pendant son premier après-midi en
direct, dont deux — l'objectif posé sur le niveau de cassure, et l'absence
d'objectif quand la cassure prend l'extrême de la séance — le rendaient
**incapable par construction de prendre un trade rentable**. Ils ont été trouvés
parce qu'un humain lisait le graphique à côté.

D'où l'ordre recommandé : faire tourner en lecture seule, comparer les signaux à
sa propre lecture, et n'activer `--live` que lorsque les signaux tiennent. Un
backtest sur un historique M1 long (export FX Replay, Dukascopy, Polygon)
resterait la seule façon de mesurer la fréquence, le taux de réussite et
l'espérance réelle.
