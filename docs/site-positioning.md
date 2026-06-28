# Site Positioning — Vantage & Wake

> **Handoff note** for the Claude Code instance building Kinetic's personal
> website. This is the intended naming and positioning for two related projects
> when they're featured on the projects page. Read this before writing or
> updating their copy.

## TL;DR

Two projects, named as a deliberate **pair**, to be featured together:

- **Vantage** — an AI market-research partner. Codebase: `vantage`
  (`~/code/python/vantage`).
- **Wake** — a portfolio tracker + decision-analysis tool. Codebase: `wake`
  (`~/code/python/wake`).

They form one system: **Vantage looks ahead at the market; Wake looks back at
your decisions — and Vantage reads from Wake** (it grounds its market analysis
in your real holdings and trading history). Present them as connected, not as
two unrelated repos.

> The code directories are `vantage` and `wake` (renamed from `market_insights`
> / `portfolio_analysis` to match the brand). GitHub repo URLs may still use the
> old names until renamed on GitHub.

## What each one is (for accurate copy)

**Vantage** — AI-driven market radar. Screens a ~915-ticker universe for
return leaders, volume spikes, and sector momentum; a Claude analyst (with live
web search) fuses those signals with sourced news to surface emerging trends,
narrative↔price convergence, and non-obvious second-order plays *before*
consensus. It's grounded in the user's real portfolio and is built to
**challenge** their reasoning, not just inform. Two modes: a proactive weekly
emailed brief, and an interactive conversational analyst (terminal chat that can
pull live data and re-run the screen on demand). Not financial advice.

**Wake** — portfolio history + decision analysis. Tracks current holdings and
the full transaction history (sector / asset-type / per-asset breakdowns),
backed by a MySQL database, with a dashboard. Its "hypotheticals" analysis
replays past decisions and patterns to show how the user could have done better
— turning hindsight into sharper future decisions.

## Chosen names & copy (⭐ = recommended)

### Vantage
**Tagline (⭐):** *See where the market's headed.*
Alternates: *Catch the trend before it's consensus.* · *The market from a
better angle.* · *An AI analyst that argues back.*

**One-line descriptor:**
> An AI research partner that scans the market for blind spots, sources its own
> news, and pressure-tests your thesis — grounded in your real holdings.

### Wake
**Tagline (⭐):** *Learn from where you've been.*
Alternates: *Every trade leaves a trail.* · *Hindsight, made useful.* · *The
full story of your portfolio.*

**One-line descriptor:**
> Tracks your complete holdings and trading history, then replays past decisions
> to turn hindsight into sharper ones.

### Connective line (use where the two are shown together)
**Recommended (⭐):** *Vantage reads from your Wake.* — accurate (Vantage pulls
from Wake's data) and quietly clever (perspective gained from the trail you've
left).

Longer "about" variant: *Wake records every decision; Vantage reads it to
sharpen the next one.*

Other variations to choose from:
- *Vantage looks ahead. Wake looks back.*
- *One reads the market. One reads you.*
- *Two halves of one system: Wake records your decisions, Vantage challenges them.*
- *Your wake shows where you've been; your vantage shows what's ahead.*

### Matched-set display (taglines mirrored)
> **Vantage** — *See where the market's headed.*
> **Wake** — *Learn from where you've been.*

## Intent for the page

- Feature **Vantage** and **Wake** as a connected pair (e.g. adjacent cards, or
  one section), with the connective line between/under them so the relationship
  reads as intentional.
- Keep the copy clean and a little understated — that's the chosen aesthetic
  (the names were picked over flashier options for being clean and cool).
- It's fine to mention the tech honestly (Python; Claude / `claude-opus-4-8`
  with web search and tool use; MySQL for Wake) if the site lists stacks.
