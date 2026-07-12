# Landing page AI Footprint (EN + FR) — design

## Contexte

AI Footprint n'a aujourd'hui qu'un README comme vitrine. Ce sous-projet livre une
landing page produit, bilingue (anglais + français), pour présenter l'outil à des
visiteurs non-développeurs ou pressés. C'est le premier des trois sous-projets
identifiés (landing page → site de documentation → traduction des skills) ; les deux
suivants seront brainstormés séparément une fois celui-ci implémenté.

## Objectif

Une page statique, honnête sur ses limites (fourchettes, pas de faux chiffre
précis — cohérent avec le positionnement produit), qui convertit un visiteur en
installation (`curl … | bash`) ou en lecture de la doc.

## Hébergement & structure technique

- **GitHub Pages, dossier `/docs` sur `main`** (pas de branche `gh-pages` séparée,
  pas de pipeline CI de build).
- **HTML/CSS statique pur** — pas de framework, pas de générateur de site, pas de
  build step. Cohérent avec YAGNI : une landing page n'a pas besoin de plus.
- **`/docs/index.html`** = version anglaise (racine — audience GitHub par défaut).
- **`/docs/fr/index.html`** = version française.
- **Cohabitation avec le futur site de doc** : la landing reste le point d'entrée
  de `/docs`. Le site de documentation (sous-projet séparé, brainstormé
  ultérieurement) occupera un sous-dossier (ex. `/docs/site/` ou `/docs/guide/`),
  sans reprendre la racine.
- Assets partagés (CSS, images) dans `/docs/assets/`, réutilisés par les deux
  langues pour éviter la duplication de style.

## Structure de la page (identique EN/FR, contenu traduit)

Dans l'ordre :

1. **Nav** — logo/nom du produit, lien vers la doc (provisoire : pointe vers
   `CONTRIBUTING.md` sur GitHub tant que le site de doc n'existe pas), lien vers
   le dépôt GitHub, bascule de langue (EN ⇄ FR).

2. **Hero** — statement qualitatif fort, pas de chiffre précis en avant-plan
   (principe validé en brainstorming : rester cohérent avec « pas de faux chiffre
   précis » porté par le reste du produit). Exemple de ton : « Chaque prompt a un
   coût — invisible, mais réel. » Sous-titre : explique en une phrase les 5
   critères mesurés + la promesse de transparence (fourchettes). Juste sous le
   sous-titre, un **badge de confiance** : « Calculé avec EcoLogits — moteur
   open source reconnu, offline, aucun chiffre inventé », avec lien vers le dépôt
   EcoLogits (https://github.com/mlco2/ecologits). Objectif : crédibiliser
   immédiatement la source des chiffres, pas seulement dans une section plus bas.
   Deux CTA : « Installer » (ancre vers la section Comment ça marche ou commande
   copiable) et « Voir la doc ». Emplacement pour un aperçu visuel (image ou GIF
   de la statusline / du rapport — production du média hors scope, cf. § Hors
   scope).

3. **Comment ça marche** — 3-4 étapes : installer (one-liner `curl … | bash`) →
   utiliser Claude Code / OpenCode / Pi normalement → voir le rapport / la
   statusline. Objectif : rassurer sur le zéro-configuration.

4. **Les 5 critères mesurés** — reprend le tableau du README (GWP 🌍 gaz à effet
   de serre, Eau 💧, ADPe ⛏ épuisement des ressources, Énergie ⚡ électricité, PE
   🔥 énergie primaire), avec une explication courte de chaque critère en langage
   accessible (pas de jargon EcoLogits non expliqué).

5. **Pourquoi des fourchettes** — section pédagogique sur l'incertitude
   irréductible (région exacte des datacenters inconnue, PUE variable), reprise du
   raisonnement du README/METHODOLOGY.md. Argument de différenciation vis-à-vis
   d'outils qui affichent un chiffre unique invérifiable. **Insiste sur la
   provenance des calculs** : AI Footprint ne réinvente pas de modélisation, il
   délègue à EcoLogits — moteur reconnu, open source, vérifiable, utilisé par
   d'autres projets de la communauté (pas une boîte noire propriétaire). Lien vers
   `docs/METHODOLOGY.md` sur GitHub et vers le dépôt EcoLogits pour le détail.

6. **Multi-outils** — mention de Claude Code, OpenCode/CRUSH, Pi : rassure chaque
   audience qu'elle est couverte par l'installeur.

7. **Footer** — lien vers le dépôt GitHub + mention de la licence, crédit à
   EcoLogits comme moteur de calcul sous-jacent, bascule de langue (redondante
   avec la nav, utile en bas de page longue), lien vers la doc/CONTRIBUTING (même
   cible que le lien nav).

## Contenu dupliqué EN/FR

Les deux fichiers (`index.html`, `fr/index.html`) portent le même contenu
traduit, pas de système de templating/i18n — cohérent avec le choix HTML/CSS pur.
La traduction est un travail éditorial, pas un problème technique : un plan
d'implémentation listera le texte final des deux langues section par section.

## Hors scope de ce sous-projet

- Le site de documentation complet (sous-projet suivant, spec séparée).
- La traduction des skills en anglais (sous-projet suivant, spec séparée).
- La production des médias réels (image/GIF de la statusline ou du rapport) : la
  landing prévoit l'emplacement, le plan d'implémentation peut soit utiliser un
  placeholder soit décrire comment produire le média, à trancher à ce moment-là.
- Analytics/tracking : aucune mention, aucun outil de mesure d'audience n'est
  demandé — pas d'ajout non sollicité.

## Critères de succès

- `docs/index.html` et `docs/fr/index.html` existent, partagent les mêmes
  sections dans le même ordre, contenu traduit fidèlement.
- La page s'affiche correctement en local (ouverture directe du fichier ou
  serveur statique simple) sans dépendance externe cassée.
- Le lien de bascule de langue fonctionne dans les deux sens.
- Aucun framework/dépendance de build introduit.
