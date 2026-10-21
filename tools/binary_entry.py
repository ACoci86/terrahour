"""Entry point for the prebuilt executables (PyInstaller needs a plain script, not a package)."""
import os
import sys

# The Linux binary ships the OpenSSL library from the build machine (Ubuntu), which only looks for
# certificates in Ubuntu's folder. On other distros (Gentoo, Arch, Fedora, Alpine...) that folder does
# not exist, so every HTTPS request fails with CERTIFICATE_VERIFY_FAILED (issue #23). Point OpenSSL at
# the system's own bundle before anything imports ssl; fall back to the certifi copy packed in the binary.
_SYSTEM_CA_BUNDLES = (
    "/etc/ssl/certs/ca-certificates.crt",                 # Debian, Ubuntu, Gentoo, Arch, Alpine
    "/etc/pki/tls/certs/ca-bundle.crt",                   # Fedora, RHEL, CentOS
    "/etc/ssl/ca-bundle.pem",                             # openSUSE
    "/etc/pki/tls/cacert.pem",                            # OpenELEC
    "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",  # RHEL 7+
    "/etc/ssl/cert.pem",                                  # Alpine, macOS, FreeBSD
)


def _find_ca_bundle():
    for p in _SYSTEM_CA_BUNDLES:
        if os.path.isfile(p):
            return p
    try:
        import certifi
        return certifi.where()
    except Exception:
        return None


if getattr(sys, "frozen", False) and not os.environ.get("SSL_CERT_FILE") and not os.environ.get("SSL_CERT_DIR"):
    _ca = _find_ca_bundle()
    if _ca:
        os.environ["SSL_CERT_FILE"] = _ca

from terrahour.cli import main  # noqa: E402

main()
