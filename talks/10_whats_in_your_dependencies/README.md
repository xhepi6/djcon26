# What's in Your Dependencies?

> **Speaker:** Mateusz Belczowski — Python Developer at Profil Software, Gdynia, Poland
> **Event:** DjangoCon Europe 2026

## What is this about?

Your Django project depends on dozens of packages, each running with your privileges. Attackers compromise these packages through typosquatting, phishing maintainers, hijacking CI/CD pipelines, and exploiting abandoned accounts. This talk walks through real incidents and builds a practical defense toolkit.

## The Problem

- **Every dependency is code that runs as you** — `pip install` executes `setup.py` with full system access. No sandboxing
- **Attacks are not theoretical** — typosquatted packages have sat on PyPI for over a year before detection
- **The attack surface is huge** — a typical Django project pulls in 50-100+ transitive dependencies
- **Detection is slow** — compromised packages often go unnoticed for days, weeks, or months
- **AI tools make it worse** — LLMs sometimes suggest installing packages that don't exist, creating opportunities for attackers to register those names

## Real Incidents

### Typosquatting

| Package | What happened | Impact |
|---------|---------------|--------|
| `jeIlyfish` (capital I, not L) | Impersonated `jellyfish`. Stole SSH and GPG keys | On PyPI for ~1 year (2019) |
| `python3-dateutil` | Paired with jeIlyfish. Looked like the real `dateutil` | Discovered by a German developer |
| Colorama typosquats | 500+ fake variations deployed zgRAT malware | Used a fake PyPI mirror domain (2024) |

### Phishing maintainers

In August 2022, attackers sent emails impersonating PyPI with a fake "mandatory validation" link. Maintainers of `deep-translator`, `exotel`, and `spam` had their credentials stolen. Malicious versions were published under their accounts.

### CI/CD pipeline attacks

**Codecov (2021):** Attackers modified Codecov's Bash Uploader script via leaked Docker credentials. For ~2 months, it exfiltrated environment variables (API keys, tokens) from 23,000+ customers including Twilio and HashiCorp.

**Ultralytics YOLO (2024):** Attackers exploited GitHub Actions `pull_request_target` trigger + template injection via a branch name. Injected a crypto miner into PyPI versions 8.3.41 and 8.3.42. The package has 30K+ GitHub stars and ~60M PyPI downloads.

### Account hijacking

**ctx package (2022):** Dormant for ~8 years. Attacker bought the expired domain of the maintainer's email, used PyPI password reset to take over the account. Published versions that stole AWS keys. ~27,000 malicious downloads.

### Dependency confusion

Alex Birsan (2021) breached 35+ companies (Apple, Microsoft, PayPal, Tesla) by publishing public packages with the same names as internal private packages. Package managers installed the public version because it had a higher version number. Earned $130K+ in bug bounties.

## The Defense Toolkit

### 1. Scan for known vulnerabilities

**pip-audit** (by PyPA / Trail of Bits + Google):

```bash
pip install pip-audit
pip-audit                          # scan current environment
pip-audit -r requirements.txt      # scan a requirements file
pip-audit --fix                    # auto-update vulnerable packages
pip-audit -f json                  # machine-readable output
```

Uses the OSV (Open Source Vulnerabilities) database. Also available as a GitHub Action: `pypa/gh-action-pip-audit`.

**Safety CLI:**

```bash
pip install safety
safety scan                        # scan current environment
safety scan --apply-fixes          # auto-fix vulnerabilities
```

### 2. Pin with hashes

A pinned version (`django==5.1.3`) tells pip which version to install. A hash tells pip exactly which file to accept — if the file on PyPI changes, installation fails.

**With pip:**

```bash
# Generate hashes
pip hash django-5.1.3-py3-none-any.whl

# In requirements.txt:
django==5.1.3 \
    --hash=sha256:abc123...
```

```bash
pip install --require-hashes -r requirements.txt
```

**With uv (recommended):**

```bash
uv pip compile requirements.in --generate-hashes -o requirements.txt
uv pip install --require-hashes -r requirements.txt
```

uv also defaults to "first-index" resolution, which prevents dependency confusion attacks.

### 3. Evaluate before installing

Before adding a new dependency, check:

- **[deps.dev](https://deps.dev/)** — dependency graphs, advisories, OpenSSF Scorecard
- **[Scorecard](https://scorecard.dev/)** — automated security health scores (0-10) for open source projects
- **[Socket.dev](https://socket.dev/)** — detects supply chain red flags (unstable ownership, suspicious install scripts)
- **[Libraries.io](https://libraries.io/)** — release history, maintainer activity, license info

Questions to ask:
- How many maintainers? (bus factor)
- When was the last release?
- Does it have known vulnerabilities?
- Does it use Trusted Publishing on PyPI?

### 4. Use Trusted Publishing and attestations

**Trusted Publishing** replaces long-lived API tokens with short-lived OIDC tokens tied to CI providers (GitHub Actions, GitLab). No token to steal.

**PEP 740 Digital Attestations** (GA November 2024) provide Sigstore-based proof of where a package was built. Over 132,000 packages have attestations as of March 2026.

Check attestation status: [are-we-pep740-yet](https://trailofbits.github.io/are-we-pep740-yet/)

### 5. Isolate package installation

`pip install` runs `setup.py` with full access to your system. Virtualenvs provide **zero** sandboxing — they just isolate installed packages, not the installation process.

Options:
- Run `pip install` inside a Docker container with no network after download
- Use multi-stage Docker builds — remove pip and build tools from the final image
- Run `pip-audit` in an isolated container before installing on your dev machine

### 6. Monitor continuously

- Run `pip-audit` in CI on every PR
- Use Socket.dev's GitHub app for PR-level dependency monitoring
- Subscribe to PyPI security advisories for your dependencies
- Set up Dependabot or Renovate for automated update PRs

## Experiment

The `experiment/` folder has a runnable Django project that demonstrates supply chain defense tools. Try it:

```bash
cd experiment
pip install -r requirements.txt
python manage.py migrate
```

Then run the commands:

```bash
# Scan your environment for known vulnerabilities
python manage.py audit_deps

# Evaluate a package before installing it (queries PyPI API)
python manage.py check_dep django-ninja

# Show what hash-pinned requirements look like
python manage.py show_hashes
```

Key files to explore:
- `deps/management/commands/audit_deps.py` — wraps pip-audit for Django projects
- `deps/management/commands/check_dep.py` — queries PyPI for package health info
- `deps/management/commands/show_hashes.py` — demonstrates hash-pinning workflow
- `requirements-hashed.txt` — example of a fully hash-pinned requirements file

## Key Takeaways

- **Supply chain attacks are real and increasing** — typosquatting, phishing, CI/CD exploits, account hijacking all happen regularly on PyPI
- **Pin with hashes, not just versions** — a version pin doesn't protect you if the file on PyPI gets replaced
- **Scan continuously** — run `pip-audit` in CI, not just once
- **Evaluate before you install** — check deps.dev, Scorecard, and Socket before adding a dependency
- **Minimize your attack surface** — fewer dependencies = fewer attack vectors. Consider vendoring small utilities instead of installing a package
- **AI tools can create new attack surface** — LLMs suggest non-existent packages that attackers can register

## Q&A Highlights

- **Can you defend against targeted nation-state attacks?** Realistically, not fully. Focus on isolating the blast radius — containers, least-privilege credentials, monitoring for unexpected behavior
- **Can you sandbox pip install?** Python/pip has no built-in sandboxing (unlike pnpm which blocks risky post-install scripts by default). Docker containers are the most practical option for isolation
- **The attack surface goes beyond PyPI** — IDE plugins, system packages, code formatters, and other tooling are also potential vectors

## Links

- pip-audit: https://github.com/pypa/pip-audit
- Safety CLI: https://github.com/pyupio/safety
- OSV database: https://osv.dev/
- Socket.dev: https://socket.dev/
- deps.dev: https://deps.dev/
- OpenSSF Scorecard: https://scorecard.dev/
- Sigstore: https://www.sigstore.dev/
- SLSA framework: https://slsa.dev/
- Trusted Publishing docs: https://docs.pypi.org/trusted-publishers/
- PEP 740 (attestations): https://peps.python.org/pep-0740/
- uv: https://docs.astral.sh/uv/
- GuardDog (malware detection): https://github.com/DataDog/guarddog
- "Defense in Depth" by Bernat Gabor: https://bernat.tech/posts/securing-python-supply-chain/

---
*Summarized at DjangoCon Europe 2026*
