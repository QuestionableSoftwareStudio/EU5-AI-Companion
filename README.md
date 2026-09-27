# EU5 AI Companion — AI Advisor for Europa Universalis V

[![GitHub release asset downloads](https://img.shields.io/github/downloads/QuestionableSoftwareStudio/EU5-AI-Companion/total?label=release%20asset%20downloads)](https://github.com/QuestionableSoftwareStudio/EU5-AI-Companion/releases)

**EU5 AI Companion** is a free, unofficial Windows AI advisor and save-analysis companion for **Europa Universalis V (EU5)**. It pauses the loaded campaign, creates an exact-current-date save snapshot, reads player-visible campaign data, and gives grounded explanations and strategy advice through Groq or OpenAI.

**It is not a screen-reading tool, it does not use microphone/voice control, and it is not an EU4 predecessor or mod port.** The Companion works from EU5 save-state data and keeps the player in control.

## Download EU5 AI Companion

**[Download the latest Windows installer](https://github.com/QuestionableSoftwareStudio/EU5-AI-Companion/releases/latest/download/EU5-AI-Companion-Setup.exe)**

No Python setup is required for the packaged installer.

The badge above counts all GitHub release-asset downloads. The project landing page also shows a live **installer-only download count** that excludes update ZIPs and metadata files.

> **Status:** Early public alpha. Windows only. Designed for non-Ironman Advisor Mode.

## What is EU5 AI Companion?

EU5 AI Companion is an **Europa Universalis V AI assistant, strategy advisor, and save analyzer** built to answer questions about the campaign you are actually playing instead of giving generic strategy-game advice.

Examples:

- “Why is my economy suddenly losing money?”
- “What changed in my market?”
- “What can you tell me about my government?”
- “What is my current military situation?”
- “Who am I at war with and how is the war going?”
- “What should I pay attention to before expanding?”

The Companion creates a fresh save when you ask a live-campaign question, so answers can correspond to the **exact in-game date** rather than an old monthly autosave.

## How it works

```text
Europa Universalis V
  -> Companion confirms and pauses the loaded campaign
  -> EU5 creates COMPANION_LIVE.eu5
  -> Rakaly reads the save
  -> player-visible campaign state is extracted
  -> Groq or OpenAI answers using that current state
```

For simple player-country questions, the Companion extracts a fast compact state instead of decoding the entire world. Larger market/world queries load more data only when required.

## Current features

- Exact-current-date EU5 save capture.
- Player-visible information only; fog of war is respected by design.
- Economy, treasury, markets and trade analysis.
- Government, laws, parliament, ruler/heir and other country-state inspection.
- Military and diplomacy retrieval is actively expanding beyond the country object into EU5's unit, war and diplomacy managers.
- Groq and OpenAI provider support.
- Automatic Companion mod installation/repair and active-playset enablement.
- Standalone Windows application with built-in updating.
- Stable Windows installer published through GitHub Releases.

## What EU5 AI Companion is not

To avoid confusion with unrelated “AI companion” projects:

- **No screen monitoring:** it does not watch or computer-vision-analyze the EU5 window.
- **No voice assistant:** it does not require a microphone or spoken commands.
- **No autoplay:** it does not click buttons or play EU5 for you.
- **No hidden omniscience:** the design goal is to use only information visible to the player.
- **Not an EU4 project:** this project was created specifically for **Europa Universalis V**.

## Design principles

- **Advisor, not autopilot.** The Companion explains and recommends; the player makes the decisions.
- **Exact state matters.** Advice should match the campaign at the moment the question was asked.
- **Fog of war matters.** Hidden AI-only information should not be used.
- **Learning first.** The purpose is to help players understand EU5’s simulation and gradually rely less on automation.
- **Fail closed.** If the Companion cannot positively confirm a loaded campaign, it does not request a fresh save.
- **Free project.** Gameplay features are intended to remain free.

## Current limitations

- Windows only.
- Advisor Mode is intended for non-Ironman campaigns and may disable achievements.
- This is an early alpha; some EU5 save fields still need gameplay-semantics validation.
- Economy and markets currently have the deepest specialized analysis.
- Military, diplomacy, population, estates and internal politics are being expanded iteratively.
- Localisation/display-name coverage is not complete for every internal EU5 key.

## Frequently asked questions

### Is there an AI assistant for Europa Universalis V?

EU5 AI Companion is an experimental community-built **AI assistant for Europa Universalis V**. It reads a fresh snapshot of the current EU5 campaign and gives contextual explanations and advice.

### Does EU5 AI Companion read EU5 save files?

Yes. It requests an exact-current-date EU5 save, uses Rakaly to read it, and extracts a bounded set of player-visible data for the question being asked.

### Does it monitor the screen or use computer vision?

No. EU5 AI Companion reads save-state data; it does not watch the game screen.

### Does it use voice or a microphone?

No. The current application is text-based.

### Does the AI control Europa Universalis V?

No. The AI does not play the game. It acts as an advisor while the player retains control.

### Does it work with Ironman?

Advisor Mode is designed for non-Ironman campaigns. Achievement-compatible Ironman support is not a project goal.

### Is this an official Paradox Interactive tool?

No. EU5 AI Companion is an unofficial community project and is not affiliated with or endorsed by Paradox Interactive.

## Search terms / project identity

This repository is the official source for **QuestionableSoftwareStudio EU5 AI Companion**, also describable as an **EU5 AI advisor**, **Europa Universalis V AI assistant**, **EU5 save analyzer**, **EU5 strategy companion**, and **Paradox strategy-game assistant**.

Canonical repository:

https://github.com/QuestionableSoftwareStudio/EU5-AI-Companion

## Planned next steps

- Deeper army, regiment, leader and manpower analysis.
- Alliances, subjects, diplomatic relations and active-war analysis.
- Better population, estate and internal-politics tools.
- Passive autosave monitoring for significant changes.
- Major-event explanations with concise historical context.
- Better first-run diagnostics and onboarding.

## Contributing and bug reports

Bug reports are especially useful while the project is young. Reproducible examples that include the EU5 game version, Companion version, the question asked, and the visible error/output make debugging much faster.

Use GitHub Issues for bugs and feature requests.

## Disclaimer

**Europa Universalis V** and **Europa Universalis** are trademarks of Paradox Interactive. EU5 AI Companion is an unofficial fan/community project and is not affiliated with or endorsed by Paradox Interactive.
