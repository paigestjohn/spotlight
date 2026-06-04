# Sandboxed Spotlight Execution

Spotlight supports three execution boundaries:

| Option | Boundary | Use When |
|---|---|---|
| Docker Sandboxes | Dedicated microVM with its own filesystem, network, and Docker daemon | Agent autonomy, untrusted package installs, or threat-intel OPSEC concerns are the main risk. |
| Devcontainer | Docker container with the project workspace bind-mounted | You want reproducible tools and editor integration. This is portable, but weaker isolation than a microVM. |
| Host install | Your normal shell and package managers | Lowest friction. Does not isolate PyPI/npm/OSINT CLI supply-chain risk from the host. |

## Pinned Runtime

The checked-in container pins Spotlight-managed command surfaces:

- Node `22.22.0` base image
- Base image digest `sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94`
- Direct apt packages in `container/apt-packages.txt`
- Full installed Debian package manifest in `container/dpkg-manifest.txt`
- `firecrawl-cli@1.3.1`
- `@tobilu/qmd@2.0.1`
- Python runs in a container-local virtualenv. `container/requirements.txt` is intentionally empty until a committed wrapper needs a third-party Python package.

Secrets are runtime inputs. Do not bake `.env`, API keys, OAuth state, SSH keys, browser profiles, Obsidian vaults, or agent config directories into images.

## Local Build

```bash
bash tests/sandbox-check.sh
```

The check refuses obvious secret files in the build context, builds the image, verifies key command versions, verifies the installed Debian package manifest, and runs `bash tests/smoke.sh` without spending API credits. The smoke test mounts the host workspace read-only, copies it inside the container, and runs against that copy so tests may create temporary case files without writing back to the host.

## Docker Sandboxes

When Docker Sandboxes are available, run the same repository inside the sandbox rather than directly on the host. Treat `--dangerously-skip-permissions` or equivalent agent modes as sandbox-only. The workspace mount should be the project checkout, not the user's home directory.

Do not mount these by default:

- `~/.ssh`
- cloud credential directories
- browser profiles
- global agent config directories
- Obsidian vaults

Mount a case-specific `.env` read-only only when a live investigation needs API access.

## Devcontainer

`.devcontainer/devcontainer.json` uses the same Dockerfile. It is suitable for development and repeatable smoke tests, but it shares a Docker container boundary with a workspace bind mount. Use Docker Sandboxes for stronger isolation.
