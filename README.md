# Raid Countdown Bot

Petit bot Discord permettant de créer et gérer des comptes à rebours pour des raids / événements.

Le bot affiche la date du raid selon le fuseau horaire local de chaque utilisateur Discord et conserve les raids actifs dans une base SQLite.

## Fonctionnalités

- Création d'un compte à rebours pour un raid
- Affichage en temps réel jusqu'à la seconde
- Heure automatiquement adaptée au fuseau horaire de chaque utilisateur Discord
- Liste des raids programmés
- Suppression d'un raid
- Sauvegarde automatique dans SQLite
- Restauration des raids après redémarrage du bot
- Permissions limitées aux membres ayant **Manage Server / Gérer le serveur** pour créer ou supprimer un raid
- Exécutable Windows disponible sans installation de Python sur la machine finale

## Commandes Discord

### `/raid create`

Crée un nouveau raid.

Paramètres :
- `title` : nom du raid
- `date` : date au format `DD/MM/YYYY`
- `time` : heure au format `HH:MM`

Exemple :

```text
/raid create
title: Dungeon 1
date: 20/08/2026
time: 20:00
```

Permission requise : `Manage Server / Gérer le serveur`

### `/raid list`

Affiche la liste des raids actuellement programmés.

Accessible à tous les membres.

Exemple :

```text
/raid list
```

Le bot affiche notamment l'ID interne de chaque raid, utilisé pour la suppression.

### `/raid delete`

Supprime un raid programmé.

Paramètre :
- `raid_id` : ID du raid visible dans `/raid list`

Exemple :

```text
/raid delete
raid_id: 12
```

Permission requise : `Manage Server / Gérer le serveur`

## Fichiers

Version Python :

```text
raid-countdown/
├── bot.py
├── .env
├── requirements.txt
├── raids.db
└── .venv/
```

Version Windows distribuable :

```text
RaidCountdown/
├── RaidCountdown.exe
├── .env
└── raids.db
```

`raids.db` est créé automatiquement s'il n'existe pas.

## Configuration `.env`

Le fichier `.env` doit se trouver dans le même dossier que `bot.py` ou `RaidCountdown.exe`.

```env
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
GUILD_ID=YOUR_DISCORD_SERVER_ID
```

- `DISCORD_TOKEN` : token du bot Discord
- `GUILD_ID` : identifiant du serveur Discord sur lequel les commandes sont synchronisées

> Ne jamais publier le fichier `.env` ni le token du bot.

## Lancer la version Python

```powershell
cd C:\chemin\vers\raid-countdown
.\.venv\Scripts\Activate.ps1
python bot.py
```

Pour arrêter le bot :

```text
CTRL + C
```

## Lancer la version `.exe`

Depuis PowerShell :

```powershell
.\RaidCountdown.exe
```

Ou simplement double-cliquer sur `RaidCountdown.exe`.

La console doit rester ouverte pendant que le bot fonctionne.

## Compiler le `.exe`

Activer d'abord le `.venv` :

```powershell
.\.venv\Scripts\Activate.ps1
```

Puis :

```powershell
python -m PyInstaller --onefile --name RaidCountdown bot.py
```

Le fichier final sera créé ici :

```text
dist\RaidCountdown.exe
```

Si PyInstaller n'est pas installé :

```powershell
python -m pip install pyinstaller
```

## Déploiement sur un autre serveur Discord

1. Inviter le bot Discord sur le nouveau serveur.
2. Activer le **Developer Mode** dans Discord.
3. Clic droit sur le serveur.
4. Cliquer sur **Copy Server ID / Copier l'identifiant du serveur**.
5. Remplacer `GUILD_ID` dans `.env`.
6. Lancer `RaidCountdown.exe`.

Exemple :

```env
DISCORD_TOKEN=YOUR_EXISTING_BOT_TOKEN
GUILD_ID=123456789012345678
```

Le token peut rester identique si le même bot Discord est utilisé.

## Permissions nécessaires au bot

Le bot doit disposer au minimum de :
- View Channel
- Send Messages
- Embed Links
- Read Message History

Il n'a pas besoin de la permission Administrator.

## Permissions utilisateurs

Pour `/raid create` et `/raid delete`, l'utilisateur doit disposer de :

```text
Manage Server / Gérer le serveur
```

Cela correspond généralement aux administrateurs et modérateurs du serveur.

`/raid list` reste accessible à tout le monde.

## Base de données

Le bot utilise SQLite.

La base est stockée dans :

```text
raids.db
```

Elle contient les raids actuellement actifs et permet de les restaurer après un redémarrage.

Aucun serveur SQL externe n'est nécessaire.

## Redémarrage

Si le bot est arrêté alors que des raids sont actifs :
1. les messages restent sur Discord ;
2. les raids restent enregistrés dans `raids.db` ;
3. au prochain lancement, le bot retrouve les raids ;
4. les comptes à rebours reprennent automatiquement au bon temps restant.

## Fuseaux horaires

Lorsqu'un raid est créé, l'heure saisie correspond à l'heure locale de la machine qui exécute le bot.

Discord affiche ensuite la date du raid selon le fuseau horaire de chaque utilisateur.

Le compte à rebours reste identique pour tous les utilisateurs.

> Si le bot est déplacé plus tard sur un VPS configuré dans un autre fuseau horaire, cette partie devra être adaptée.

## Version actuelle

V1 :
- [x] `/raid create`
- [x] `/raid list`
- [x] `/raid delete`
- [x] Compte à rebours en temps réel
- [x] SQLite
- [x] Restauration après redémarrage
- [x] Fuseaux horaires Discord
- [x] Permissions admin/modo
- [x] Version `.exe` Windows
- [x] Lancement manuel

Fonctionnalités possibles plus tard :
- rappels automatiques avant un raid
- boutons d'inscription
- édition d'un raid
- rôle Raid Leader configurable
- lancement automatique avec Windows
- logs dans un fichier
- gestion multi-serveurs plus avancée
