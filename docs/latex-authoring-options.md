# Browser LaTeX authoring options

Checked November 3, 2026. This note records an assessment of established editors
for chapter-based browser writing and PDF compilation. It does not report an
editor deployment or a manuscript migration.

## Requirements and product choice

The intended workflow needs editable chapter files, a rendered PDF, comments,
tracked changes, the official university template, and recoverable private
source. These requirements should be checked before choosing where the editor
runs. An upstream product can be deployed or linked without maintaining a fork
of its application code.

| Route | Relevant capability | Condition to check |
|---|---|---|
| Hosted Overleaf | Browser source editing and PDF compilation; premium review and synchronization features where enabled | Account access, actual entitlement, template compilation, sharing permissions and export |
| Overleaf Community Edition through the official Toolkit | Self-hosted source editing and project history | Maintained application host and fully trusted users; built-in comments, tracked changes, SSO and Git integration are absent |
| Overleaf Server Pro | Self-hosting with the documented review, integration and sandbox options | Commercial license, supported configuration, operating resources and recovery checks |

The [Overleaf edition comparison](https://docs.overleaf.com/on-premises/welcome/server-pro-vs.-community-edition)
documents these feature boundaries. Community Edition expects every user to be
trusted with the resources available to its compilation container. Project-level
permissions do not establish isolation between untrusted researchers. The
[official installation introduction](https://docs.overleaf.com/on-premises/installation/introduction)
recommends starting an on-premises evaluation with the Toolkit.

ÉTS lists a requestable Overleaf Cloud premium license through GUS, including
GitHub synchronization, full history and tracked changes. Access comes from a
limited pool and can be removed; the university states that documents remain
intact and users can apply again. This is an available request route, not proof
that an individual account has premium access. See the
[ÉTS IT services page](https://www.etsmtl.ca/experience-etudiante/services-informatiques).

## Roles of the website and cloud services

A research website can link to an authenticated editor without running that
editor. GitHub can hold a private source repository and versioned backups;
repository visibility must be checked before transferring unpublished work.
GitHub Pages itself serves static sites. GitHub Codespaces supplies a separate
computing environment, so it should not be confused with Pages. See
[GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
and the [Codespaces lifecycle](https://docs.github.com/en/codespaces/about-codespaces/understanding-the-codespace-lifecycle).

Firebase Hosting can route requests to a Cloud Run container. That is a backend
deployment decision, rather than a consequence of storing text in a database.
Cloudflare also offers Containers in addition to static Pages. Cloudflare's
container disk is temporary by default, and Cloud Run's writable filesystem does
not persist when an instance stops. A stateful editor therefore needs a tested
storage and recovery design on either route. These platforms are not ruled out;
a stock Overleaf deployment on them has not been established here. See
[Firebase Hosting with Cloud Run](https://firebase.google.com/docs/hosting/cloud-run),
[Cloudflare Containers](https://developers.cloudflare.com/containers/faq/), and
[the Cloud Run runtime contract](https://docs.cloud.google.com/run/docs/container-contract#file_system_access).

## Template and migration checks

Use the [official ÉTS template source](https://www.etsmtl.ca/en/programs-training/writing-guidelines-and-templates),
preserving its notices and degree options. The template files are not
redistributed in this repository. A private template-only prototype has been
organized into separate chapter files. The local check stopped at a missing font
package in the existing minimal TeX runtime; it produced no PDF. This does not
establish whether the template compiles in the intended hosted environment.

Before a cutover, compile the official template in the selected editor, import
a recoverable source copy, check references and figures, and exercise comments
and tracked changes. Test sharing permissions and an export-and-restore cycle.
A working website link, a rendered PDF, and a verified backup establish different
things. Existing review edits must be reconciled before a replacement manuscript
becomes authoritative.

Hosted Overleaf with a verified institutional Cloud seat is the preferred
starting candidate for the stated review features. Whether the editor itself
must run on a personally controlled domain remains open. Separate Google Gemini
and xAI Grok critiques of public-source deployment options supported evaluating
hosted access first and avoiding an unnecessary deep fork. Their critiques did
not test a deployment, template, account or backup. Current platform capability
checks also do not establish an operational Cloudflare or Cloud Run installation.
