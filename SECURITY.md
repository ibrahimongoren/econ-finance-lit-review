# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 2.0.x | Yes |
| 1.0.x | No; please upgrade to 2.0 |

## Scope

The skill runs inside Claude and calls third-party scholarly services with the user's own
credentials. Reports are particularly welcome on:

- exposure of API keys or institutional tokens, for example a script that prints or logs a key or
  writes it to a review folder;
- any code path that contacts a shadow library (Sci-Hub, LibGen or their mirrors) or circumvents a
  provider's access controls (CAPTCHAs, bot detection, rate limits or institutional
  authentication);
- unsafe handling of imported files (RIS, BibTeX, CSV, JSON) or of content retrieved from the web;
- example configuration files in [`integrations/`](integrations/README.md) that grant broader
  permissions than documented.

Inaccurate references (a fabricated, mismatched or retracted source that passed verification) are
quality defects rather than security issues; please report them through the *Verification
failure* issue form.

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private vulnerability
reporting instead: open the **Security** tab of this repository and select **Report a
vulnerability**. Include the affected file and version, the steps to reproduce and the potential
impact. Reports are acknowledged as soon as possible, and fixes are coordinated with the reporter
before public disclosure.

If an API key has been committed by mistake, revoke it with the provider immediately; removing it
from the repository history does not make it safe to use again.
