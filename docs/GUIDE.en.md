# User guide

How to use `ai-footprint`: installation, uninstallation, and everyday use of
the skills. For a quick overview of the product, see the
[README](https://github.com/hrenaud/ai-footprint#readme); to understand how
impacts are calculated, see [METHODOLOGY.md](METHODOLOGY.md).

`ai-footprint` works with **Claude Code**, **Opencode**, and **Pi**: the
installer automatically detects the tools present on your machine and
enables skills/tracking for each of them, with nothing to configure
yourself.

## Installation

### Prerequisites

- Python ≥ 3.10.
- Chrome or Chromium installed locally, only if you plan to use
  `/footprint-card` (exporting your footprint as an image).

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/install.sh | bash
```

This command installs `ai-footprint`, enables it for all compatible tools
detected on your machine (Claude Code, Opencode, Pi), and backfills your
past session history. **Restart your tool** (Claude Code, Opencode, or Pi)
once the installation is done to activate the skills.

### Update

Simply rerun the install command above: it updates `ai-footprint` without
losing your history. An available update is also proposed to you
automatically at the start of a session.

## Uninstallation

```bash
curl -fsSL https://raw.githubusercontent.com/hrenaud/ai-footprint/main/uninstall.sh | bash
```

This command removes `ai-footprint` from every tool where it was active.
**Your impact history is kept by default** — to delete it too, see the
[advanced guide](GUIDE-AVANCE.md#complete-uninstallation).

## Using the skills

This is the recommended way to use ai-footprint: type the slash command, or
simply ask in natural language (the skills also trigger on phrasing like
"my impact" or "my CO₂ footprint").

### `/footprint-report` — the full report

Displays the multi-criteria impact of your sessions:

- **Total impact** — the five criteria (GWP, water, ADPe, energy, primary
  energy), as a min–max range.
- **Most impactful projects** — breakdown by working directory.
- **Tokens & impact per model** — which model consumes the most.
- **Uncovered models** — models whose impact could not be estimated. See
  `/footprint-resolve` below to resolve them.
- **Intensity per model** — impact per hour of work (reveals that, at an
  equal work rate, a bigger model like Opus emits far more than a lighter
  model like Haiku).
- **Intensity per tool** (as soon as your data covers several tools) —
  which tool consumes the most, at an equal rate.

You can filter on a period ("since June 27", for example), or ask for the
detail per model/project.

### `/footprint-card` — export as an image

Generates a shareable image summarizing your footprint: carbon as the hero
figure, the other criteria (water, energy, metals, primary energy) as
tiles, and the top 3 most impactful projects. Requires Chrome or Chromium.

### `/footprint-resolve` — resolve uncovered models

Some models (third-party, local, or too recent) are out of the calculation
engine's scope: ai-footprint keeps the event but excludes its impact from
the totals rather than displaying a made-up number. This skill proposes,
for each uncovered model, a mapping to a known equivalent model, and
recalculates the impacts after your confirmation.

Triggers automatically as a proposal at the start of a session if relevant,
or manually at any time.

### `/footprint-config` — settings

Adjusts the assumptions used for the calculation (electricity mix zone,
datacenter efficiency…). Detected automatically on the first report if not
already set.

### `/footprint-help` — help

Displays ai-footprint's actual help: all available commands.

## Real-time tracking

Once installation is complete, your tool continuously displays the impact
of the **current session**, for example:

```
⚡ 18.9–33.5 kWh · 🌍 7.93–13.5 kgCO2e · 💧 61.3–134 L
```

A `≈` prefix signals that the session uses a model too recent to be
precisely measured: the displayed impact is then a provisional reference —
see
[METHODOLOGY.md](METHODOLOGY.md#anthropic-models-too-recent-for-the-ecologits-registry).

## Going further

- **[Advanced guide](GUIDE-AVANCE.md)** — manual installation (Homebrew,
  PyPI, from source), environment variables, and how ai-footprint works
  under the hood.
- **[METHODOLOGY.md](METHODOLOGY.md)** — how impact is evaluated: the
  exchanges with EcoLogits, methodological choices and their limits.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — the technical side: architecture,
  data schema, dev setup, and how to extend the project.
