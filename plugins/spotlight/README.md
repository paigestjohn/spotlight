# Spotlight Plugin

This plugin installs Spotlight's agent-facing skills, agents, schemas, and
operator documentation.

Plugin install does not install runtime packages. It must not run `pip install`,
`npm install`, `uv tool install`, `npx`, or equivalent dependency commands.

For a full local runtime with reviewed dependency pins, use `setup.html` from
the repository root. The setup installer uses exact versions recorded in
`VALIDATED_DEPENDENCIES.md`.

RLM is optional and off by default. If a user enabled RLM during setup,
Spotlight proposes it during methodology approval for each case. RLM output is
lead-only and never verified or publishable evidence.
