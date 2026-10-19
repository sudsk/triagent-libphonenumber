# triagent-libphonenumber

libphonenumber-specific wiring for [triagent](https://github.com/sudsk/triagent): the
`profile.json` triagent's registry (`agents/profiles.py`) reads to learn this repo's identity,
plus the Cloud Run Sandbox dispatcher image Builder/Judge/Bug Prover use when running against
libphonenumber.

## Layout

- `profile.json` — identity (upstream/fork/app_name) and wiring (test-command template, sandbox
  setup command) that triagent's dashboard and pipeline read for `repo_id = "libphonenumber"`.
  `dispatcher_url` stays `null` here permanently and on purpose — this is a public repo, and a
  deployed Cloud Run dispatcher's URL shouldn't sit in a public repo's git history even though the
  service itself is IAM-locked. Once this repo's dispatcher image (below) is deployed, its real
  URL goes into the `TRIAGENT_DISPATCHER_URL_LIBPHONENUMBER` env var on whichever host runs the
  dashboard or pipeline (gitignored `.env`, see `triagent`'s `.env.example`) —
  `agents/profiles.py`'s `resolve_dispatcher_url` checks that before this file's own (null) field.
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
