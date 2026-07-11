# Publication PyPI — actions manuelles restantes

Ce document couvre les deux actions qui ne peuvent être faites que par le
titulaire du compte PyPI (`renaud.heluin@novagaia.fr` ou équivalent), donc pas
automatisables par l'agent. Tout le reste (workflow CI, paquet coquille) est
déjà en place — voir [`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml)
et [`packaging/agent-footprint/`](../packaging/agent-footprint/).

## 1. Déclarer le Trusted Publisher pour `ai-footprint`

Le workflow `publish-pypi.yml` publie automatiquement sur PyPI à chaque tag
`v*` (créé par `ai-footprint release bump`), via **Trusted Publishing (OIDC)** :
aucun token/secret stocké, l'authentification se fait par la confiance
déclarée entre le projet PyPI et le repo GitHub + workflow.

**Prérequis** : le projet `ai-footprint` doit exister sur PyPI. S'il n'existe
pas encore, la première publication doit être faite manuellement avant de
pouvoir configurer le Trusted Publisher (PyPI exige que le projet existe déjà,
sauf à utiliser un "pending publisher", cf. § 3 ci-dessous).

**Étapes** (une fois le projet créé) :

1. Se connecter sur [pypi.org](https://pypi.org) avec le compte propriétaire.
2. Aller sur la page du projet → **Manage** → **Publishing**.
3. Dans la section **Trusted Publishers**, cliquer **Add a new publisher** →
   choisir **GitHub**.
4. Renseigner :
   - **Owner** : `hrenaud`
   - **Repository name** : `ai-footprint`
   - **Workflow name** : `publish-pypi.yml`
   - **Environment name** : `pypi` (correspond à `environment: pypi` déclaré
     dans le workflow)
5. Valider. Aucune autre configuration côté GitHub n'est nécessaire — le
   workflow est déjà écrit pour ce flux (`permissions: id-token: write`).

**Vérification** : pousser un tag `v*` (via `.venv/bin/ai-footprint release
bump <patch|minor|major>`) et vérifier que le job `publish` du workflow
`publish-pypi.yml` passe au vert dans l'onglet Actions du repo.

## 2. Publier `agent-footprint` (paquet coquille)

Le paquet [`packaging/agent-footprint/`](../packaging/agent-footprint/)
redirige `pip install agent-footprint` vers `ai-footprint`, pour qui cherche
l'ancien nom du projet. Il n'est pas couvert par le workflow CI (celui-ci ne
publie que `ai-footprint`) : sa publication est un geste ponctuel, à refaire
seulement en cas de changement de version.

**Étapes** :

```bash
cd packaging/agent-footprint
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

`twine upload` demande un identifiant PyPI — utiliser soit un token API
PyPI (`__token__` comme nom d'utilisateur, le token comme mot de passe),
généré depuis **Account settings → API tokens** sur pypi.org, soit configurer
un Trusted Publisher dédié à ce second paquet si des publications répétées
sont prévues (mêmes étapes que § 1, avec un repo/workflow séparé, puisque
Trusted Publishing est lié à un repo GitHub précis — or `agent-footprint`
n'a pas de repo ni de workflow CI propre pour l'instant).

Nettoyer ensuite les artefacts de build locaux (`dist/`, `*.egg-info/`) avec
`trash`.

## 3. Ordre recommandé

1. Publier `ai-footprint` une première fois manuellement (`python -m build` +
   `twine upload` depuis la racine du repo) — ou déclarer un **pending
   publisher** sur PyPI (Trusted Publishers → "Add" avant même que le projet
   existe) pour laisser la première publication passer directement par la CI.
2. Configurer le Trusted Publisher (§ 1) si ce n'est pas déjà fait via le
   pending publisher.
3. Publier `agent-footprint` (§ 2), une fois `ai-footprint` disponible sur
   PyPI (c'est sa dépendance).
