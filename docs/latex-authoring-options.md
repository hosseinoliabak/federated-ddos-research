# Browser LaTeX authoring options

Checked November 3, 2026. The editor itself must run under a personally controlled
domain. Comments, tracked insertions and deletions with acceptance or rejection,
chapter files, PDF compilation and recoverable private projects are required.
The present workspace remains active. No replacement service or manuscript
migration is reported here.

## Candidate comparison

| Candidate | Review workflow | Remaining fit checks |
|---|---|---|
| Ayakaleaf Pro | Public source implements tracked edits, accept/reject and anchored comments | Pinned deployment, effective compilation isolation, university template, access, recovery and maintenance |
| Overleaf Server Pro | Official documentation includes comments, real-time tracking and sandboxed compilation | Separate commercial license, supported host, configuration and the same operational checks |
| TeXlyre | Native comments and tracked insertions/deletions with accept/reject | Browser-local accounts and bearer sharing do not establish centrally authenticated, durable private projects |

The leading open-source candidate for a synthetic stack trial is
[Ayakaleaf Pro](https://github.com/ayaka-notes/ayakaleaf-pro), an independent
community fork. This is a trial choice rather than production approval. The
source inspection used commit `2b5d8208b03d5d3654e01673cc3122456db144e5`.
Its [review routes](https://github.com/ayaka-notes/ayakaleaf-pro/blob/2b5d8208b03d5d3654e01673cc3122456db144e5/services/web/modules/track-changes/app/src/TrackChangesRouter.mjs)
apply authorization checks, and its
[review actions](https://github.com/ayaka-notes/ayakaleaf-pro/blob/2b5d8208b03d5d3654e01673cc3122456db144e5/services/web/frontend/js/features/review-panel/hooks/use-tracked-changes-actions.ts)
implement separate accept and reject operations. Its
[Docker runner](https://github.com/ayaka-notes/ayakaleaf-pro/blob/2b5d8208b03d5d3654e01673cc3122456db144e5/services/clsi/app/js/DockerRunner.mjs)
defines project-specific compilation mounts and resource/network restrictions.
Source and test presence do not establish passing runtime behavior. A proposed
trial pins application release `6.3.2` at image index digest
`sha256:5f84c7f2d0230dd558130ca2901f603d4e0bfe021054879efea1b7fece2f4f1c`
and the matching release source `925980d35f22b89931a28873db38de2d72d35cc6`.
The inspected release review routes, controller, authorization middleware and
Docker runner match the corresponding audited files. Other source and runtime
behavior remain subject to the trial.

The fork publishes AGPL-3.0 license files and
[component attribution](https://ayakaleaf-pro.ayaka.space/on-premises/readme/features-and-copyright).
This limited inspection did not audit every dependency or image. Preserve
copyright and license notices, pin the actual image, and assess updates before
hosting. The root Compose file and an unchanged Toolkit seed do not establish
the intended configuration. Deliberately select the fork and verify that
sandboxed compilation is actually active.

The [official Overleaf comparison](https://docs.overleaf.com/on-premises/welcome/server-pro-vs.-community-edition)
documents Server Pro's relevant features and separate licensing. A Cloud Pro
subscription does not grant Server Pro access. Community Edition lacks the
requested review features and expects trusted users, so an unchanged CE
installation is insufficient. Server Pro remains a supported-product
alternative, subject to a quote and the operating work required for self-hosting.

[TeXlyre](https://github.com/TeXlyre/texlyre) is a credible browser editor with
real tracking rather than only version diffs. However, its
[account documentation](https://texlyre.github.io/docs/accounts/account-types)
describes browser-local projects, and its
[sharing documentation](https://texlyre.github.io/docs/collaboration/sharing-projects)
gives project-link holders read/write access. Native backups and peer sync are
useful capabilities, but their existence does not demonstrate a private project
that reappears through sign-in after the original browser closes. Adding central
storage and authorization would be integration work with its own tests.

A local TeXlyre `v0.13.5` prototype at commit
`92b50ca050af8473f0fd51a048a7e1d60dcdb2dc` imported the 19-file public-template
prototype and opened its chapter tree. Native tracked insertion acceptance and
rejection, deletion rejection, and comment/edit persistence after reload were
checked with dummy content. A fresh browser profile could not sign in with the
first profile's dummy account. This directly confirms the account-storage limit
for the intended workflow. Native export/import into a separate local account
preserved the comment and pending insertion, which is a tested manual recovery
route. Immediate comment visibility failed one assertion, although the note
appeared after reload and import. A nonfatal application error also occurred.
The complete university-template PDF build was not run in this browser trial.

Aldine was also considered. It offers comments and suggested replacements, but
its [documented comparison](https://aldine.dev/self-hosted-overleaf/) distinguishes
these from continuous tracked editing. Its
[scaling notes](https://github.com/trahloff/Aldine/blob/main/docs/SCALING.md)
identify shared-compiler isolation as unfinished for independent tenants. These
limits make it a less direct match to the stated review and future-user goals.

## Hosting roles

A conventional Linux VM with durable disk is the closest architectural match to
the inspected Overleaf-style stack. It can run the application, MongoDB, Redis
and the Docker daemon used for separate compilation containers. This is an
engineering inference from the
[documented dependencies](https://docs.overleaf.com/on-premises/getting-started/requirements/software-requirements)
and [sandbox architecture](https://docs.overleaf.com/on-premises/configuration/overleaf-toolkit/server-pro-only-configuration/sandboxed-compiles),
not an executed deployment or a request for another physical server. A cost
estimate and authorization must precede any paid provisioning.

Cloudflare offers real Containers, including Docker-in-Docker support. Its
[FAQ](https://developers.cloudflare.com/containers/faq/) describes temporary
default storage and persistence options. This does not establish reliable
MongoDB, project history or restore behavior for this application. Cloud Run's
[runtime contract](https://docs.cloud.google.com/run/docs/container-contract)
also describes temporary writable storage and excludes privileged containers.
Neither platform is ruled out in principle, but a stock isolated Overleaf stack
on them has not been demonstrated. Building a new backend solely to fit a
hosting product would add application work to the thesis schedule.

GitHub remains useful for a private source backup and public reusable research
code. GitHub Pages serves static files, rather than this application stack.
Firebase can retain its current account/storage roles, but those roles do not
automatically implement another application's project permissions or review
metadata. See [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
and [Firebase Hosting with Cloud Run](https://firebase.google.com/docs/hosting/cloud-run).

## Migration gates

1. Compile the exact [official ÉTS template](https://www.etsmtl.ca/en/programs-training/writing-guidelines-and-templates)
   with chapter includes, French text, required fonts, figures and APA 6
   references. The existing placeholder-only source prototype has not yet
   passed this complete build.
2. Exercise comments and tracked insertion/deletion in two synthetic accounts.
   Accept one change, reject another, reload and verify both attribution and
   the compiled content. Test the actual automated editing route as well.
3. Close the original browser and recover source and review state from a fresh
   device/profile through the intended sign-in route.
4. Check private project access through HTTP, exports and real-time connections.
   Test revocation and a bounded cross-project compilation read using only
   synthetic sentinel files. Application permissions and compiler isolation
   are separate boundaries.
5. Restore source, history, users and review metadata from backup. A source ZIP
   or Git checkout alone must not be called a review-state backup.

Separate Google Gemini and xAI Grok critiques of the same public-source-only
packet completed. Both supported bounded synthetic checks and distinguished
source backups from review-state recovery. The writer rejected an inferred
zero-budget restriction and the treatment of untested fork features as absent.
The subsequent source inspection and prototype observations are separate
evidence that neither reviewer inspected. The own-domain requirement is settled.
Licensing preference, a tested runtime and operating cost remain deployment
decisions. Neither review agreement nor a working login page establishes
readiness for the private thesis.
