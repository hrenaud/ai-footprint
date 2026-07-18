# Questions interactives Codex — design

## Objectif

Rendre explicite, dans les skills qui collectent une réponse utilisateur, la
stratégie Codex : utiliser `request_user_input` lorsque le runtime l’expose,
puis conserver le repli texte existant lorsqu’il ne l’expose pas.

## Périmètre

Modifier la section « Comment poser les questions » de :

- `skills/footprint-report/SKILL.md`
- `skills/footprint-card/SKILL.md`
- `skills/footprint-resolve/SKILL.md`
- `skills/footprint-config/SKILL.md`

Chaque liste de runtimes recevra l’entrée suivante, après Claude Code :

```md
- **Codex** : utiliser `request_user_input` si l’outil est exposé par le runtime ; sinon, utiliser le repli texte numéroté ci-dessous et attendre la réponse avant de poursuivre.
```

## Comportement

Le skill ne tente pas d’activer les boutons : leur disponibilité dépend du
runtime Codex. Quand l’outil est présent, il permet des choix structurés. Quand
il est absent, les règles de fallback déjà écrites dans chaque skill restent
applicables et la commande attend une réponse avant toute exécution.

## Hors périmètre

- Aucun changement du CLI `ai-footprint` ni de son format de rapport.
- Aucun changement des entrées Claude Code, OpenCode, Pi ou MCP.
- Aucun mécanisme pour forcer l’exposition de `request_user_input` par Codex.

## Vérification

Une recherche textuelle doit confirmer l’ajout de l’entrée Codex dans les
quatre skills et la présence inchangée du fallback texte dans chacun.
