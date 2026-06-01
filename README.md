# Shotgun Tracker

Suivi automatisé des disponibilités de billets sur Shotgun.

Le projet collecte régulièrement le nombre de places disponibles pour les événements de certains organisateurs (actuellement Encore et 23:59), stocke l'historique dans une base SQLite puis génère des fichiers JSON exploitables par un site statique hébergé sur GitHub Pages.

## Fonctionnalités

* Découverte automatique des événements Shotgun d'un organisateur
* Scraping des différentes catégories de billets
* Historisation des disponibilités dans SQLite
* Génération de fichiers JSON pour le frontend
* Visualisation des disponibilités via GitHub Pages
* Suivi temporel de l'évolution des stocks de billets

## Configuration du scraping

Par défaut, le scraper clique jusqu'à ce que Shotgun désactive le bouton `+`, sans plafond artificiel à 1000 places. Le timeout par ticket reste actif pour éviter un blocage infini.

Variables utiles :

* `SHOTGUN_MAX_CLICKS` : limite optionnelle de clics par ticket. `0` ou non défini = illimité.
* `SHOTGUN_TICKET_TIMEOUT_SECONDS` : durée maximale de comptage pour un ticket, `120` secondes par défaut.


## Avertissement

:warning: Ce projet est développé à des fins de suivi statistique des disponibilités publiques affichées sur Shotgun.
