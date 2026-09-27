# EU5 AI Companion

An unofficial AI co-gamer and learning companion for **Europa Universalis V**.

EU5 AI Companion reads an exact snapshot of the player's current campaign and gives grounded, player-facing advice about what is happening and why. The player always remains in control of the game.

> **Status:** early MVP / pre-release. Windows only for now.

## What it does today

- Pauses the loaded campaign through a small Companion mod.
- Creates an exact-current-date save instead of relying on monthly autosaves.
- Decodes the save with Rakaly.
- Extracts a fast core snapshot for simple questions such as treasury/economy.
- Lazily loads the larger visible-world dataset for market and goods questions.
- Respects player-visible information rather than using hidden AI state.
- Supports Groq and OpenAI providers.
- Installs/repairs the Companion EU5 mod and enables it in the active playset.
- Runs as a standalone Windows application.

## Design principles

- **Advisor, not autopilot.** The Companion explains and recommends; it never plays the game for you.
- **Exact state matters.** Answers should describe the campaign state at the moment you asked.
- **Fog of war matters.** The advisor should only use information available to the player.
- **Learning first.** The goal is to help players understand EU5's simulation instead of merely optimizing everything for them.
- **Fail closed.** If the Companion cannot positively confirm a loaded campaign, it does not request a save.
- **Free project.** The intended public release is free; no gameplay features are planned to be paywalled.

## Current architecture

```text
EU5
  -> Companion pause event
  -> exact save
  -> Rakaly decode
  -> fast core snapshot
  -> AI answer

Detailed question
  -> same exact decoded snapshot
  -> visible-world SQLite import
  -> market/goods tools
  -> AI answer
```

Simple current-state questions avoid the full visible-world import. Detailed market/world questions load it only when needed.

## Current limitations

- Windows only.
- Advisor Mode is intended for non-Ironman campaigns.
- Economy and market understanding are currently the strongest areas.
- Some raw EU5 save fields still need gameplay-semantics validation before the Companion should make stronger causal claims from them.
- The project is still being prepared for its first public release.

## Planned next steps

- v0.1.0 packaged release.
- Built-in self-update support using GitHub Releases.
- Automated Windows builds through GitHub Actions.
- Better first-run setup and diagnostics.
- Broader military, diplomacy, population, estate and internal-politics tools.
- Passive monitoring and major-event explanations later.

## Repository

The application source, release automation, issue tracking and update metadata live here.

Bug reports and reproducible save-state problems are especially useful while the project is young.

## Disclaimer

EU5 AI Companion is an unofficial community project and is not affiliated with or endorsed by Paradox Interactive.
