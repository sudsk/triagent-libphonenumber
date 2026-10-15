# triagent-libphonenumber

libphonenumber-specific wiring for [triagent](https://github.com/sudsk/triagent): the
`profile.json` triagent's registry (`agents/profiles.py`) reads to learn this repo's identity,
plus the Cloud Run Sandbox dispatcher image Builder/Judge/Bug Prover use when running against
libphonenumber.

## Layout

- `profile.json` — identity (upstream/fork/app_name) and wiring (dispatcher URL, test-command
  template, sandbox setup command) that triagent's dashboard and pipeline read for `repo_id =
  "libphonenumber"`. `dispatcher_url` is `null` until this repo's dispatcher image (below) is
  actually deployed to Cloud Run — fill it in once that URL exists, so triagent routes
  cloudrun-mode runs to it automatically instead of needing the global `TRIAGENT_DISPATCHER_URL`
  env var swapped by hand.
- `dispatcher/` — the Cloud Run Sandbox dispatcher image, toolchain-baked for libphonenumber
  (Java 21 + Maven). Needs `TRIAGENT_SANDBOX_ALLOW_EGRESS=true` at run time — `mvn test` resolves
  dependencies against Maven Central.

## Using this with triagent

Clone this repo anywhere under `TRIAGENT_PROFILES_ROOT` (default
`~/triagent-phase1/profiles/`) — the directory name doesn't matter, triagent discovers it by
finding `profile.json`:

```
git clone <this repo's url> ~/triagent-phase1/profiles/libphonenumber
```

Onboarding data (`record.csv`, `deepwiki.md`) is separate and still lives under
`TRIAGENT_ONBOARDING_ROOT/libphonenumber/` (`agents/onboarding.py`) — that was already outside
triagent's own git history before this repo existed, so it isn't duplicated here.
