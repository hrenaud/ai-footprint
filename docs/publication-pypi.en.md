# PyPI Publication — Remaining Manual Actions

This document covers the two actions that can only be done by the holder of
the PyPI account (`renaud.heluin@novagaia.fr` or equivalent), and therefore
cannot be automated by the agent. Everything else (CI workflow, shell
package) is already in place — see
[`.github/workflows/publish-pypi.yml`](../.github/workflows/publish-pypi.yml)
and [`packaging/agent-footprint/`](../packaging/agent-footprint/).

## 1. Declare the Trusted Publisher for `ai-footprint`

The `publish-pypi.yml` workflow automatically publishes to PyPI on every
`v*` tag (created by `ai-footprint release bump`), via **Trusted Publishing
(OIDC)**: no token/secret stored, authentication relies on the trust
declared between the PyPI project and the GitHub repo + workflow.

**Prerequisite**: the `ai-footprint` project must exist on PyPI. If it
doesn't exist yet, the first publication must be done manually before the
Trusted Publisher can be configured (PyPI requires the project to already
exist, unless using a "pending publisher", see § 3 below).

**Steps** (once the project has been created):

1. Log in on [pypi.org](https://pypi.org) with the owner account.
2. Go to the project page → **Manage** → **Publishing**.
3. In the **Trusted Publishers** section, click **Add a new publisher** →
   choose **GitHub**.
4. Fill in:
   - **Owner**: `hrenaud`
   - **Repository name**: `ai-footprint`
   - **Workflow name**: `publish-pypi.yml`
   - **Environment name**: `pypi` (matches the `environment: pypi` declared
     in the workflow)
5. Confirm. No further configuration is needed on the GitHub side — the
   workflow is already written for this flow (`permissions: id-token:
write`).

**Verification**: push a `v*` tag (via `.venv/bin/ai-footprint release bump
<patch|minor|major>`) and check that the `publish` job of the
`publish-pypi.yml` workflow passes in the repo's Actions tab.

## 2. Publish `agent-footprint` (shell package)

The [`packaging/agent-footprint/`](../packaging/agent-footprint/) package
redirects `pip install agent-footprint` to `ai-footprint`, for anyone
looking for the project's former name. It isn't covered by the CI workflow
(which only publishes `ai-footprint`): publishing it is a one-off action,
to be redone only when its version changes.

**Steps**:

```bash
cd packaging/agent-footprint
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```

`twine upload` asks for PyPI credentials — use either a PyPI API token
(`__token__` as username, the token as password), generated from **Account
settings → API tokens** on pypi.org, or configure a Trusted Publisher
dedicated to this second package if repeated publications are planned
(same steps as § 1, with a separate repo/workflow, since Trusted
Publishing is tied to a specific GitHub repo — and `agent-footprint`
currently has no repo or CI workflow of its own).

Then clean up the local build artifacts (`dist/`, `*.egg-info/`) with
`trash`.

## 3. Recommended order

1. Publish `ai-footprint` manually for the first time (`python -m build` +
   `twine upload` from the repo root) — or declare a **pending publisher**
   on PyPI (Trusted Publishers → "Add" even before the project exists) to
   let the first publication go directly through CI.
2. Configure the Trusted Publisher (§ 1) if not already done via the
   pending publisher.
3. Publish `agent-footprint` (§ 2), once `ai-footprint` is available on
   PyPI (it's its dependency).
