# Security boundary

Run only for trusted, access-controlled host repositories and trusted base-branch writers.
Do not trigger a desktop runner from untrusted pull requests/forks. A runner has the desktop
user's tools and SSH identity. This is not a VM or isolation between mutually untrusted hosts.
Use `setup.ps1` from a reviewed dispatcher checkout. It installs a hash-checked local copy;
never use workflow or pull-request code as privileged runner bootstrap code.
The agent receives workspace-write and the provisioned Windows restricted-user backend;
no unsandboxed fallback is provided. Actions/GitHub/runner token environment variables are
stripped, but credentials accessible through other local mechanisms remain governed by the
machine sandbox. Raw model logs stay local; review all staged files before merge/publication.
The bridge stages all changes in its isolated clone; the host must not put secrets there.
Submodules in a host checkout are initialized at their host-pinned commits. Review their URLs
and gitlinks as trusted executable dependencies. Do not globally enable the Git file protocol.

Public source visibility does not make a host safe to dispatch. Trust and authorization come
from the host repository, its access control and each Ready work item.
Disable the workflow/stop the runner to suspend dispatch; retain claims and recovery files.
