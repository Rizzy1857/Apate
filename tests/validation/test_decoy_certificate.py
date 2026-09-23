from cryptography import x509
from cryptography.hazmat.primitives import serialization
from chronos.intelligence.deterministic_renderer import DeterministicRenderer


def test_decoy_certificate_valid_matching_and_reproducible():
    renderer = DeterministicRenderer()
    state = {'hostname': 'web01'}
    cert_bytes = renderer.render('/etc/ssl/certs/ssl-cert-snakeoil.pem', state)
    key_bytes = renderer.render('/etc/ssl/private/ssl-cert-snakeoil.key', state)
    certificate = x509.load_pem_x509_certificate(cert_bytes)
    key = serialization.load_pem_private_key(key_bytes, password=None)
    certificate.public_key().verify(certificate.signature, certificate.tbs_certificate_bytes)
    assert key.public_key().public_bytes_raw() == certificate.public_key().public_bytes_raw()
    assert certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName) == ['web01']
    assert cert_bytes == DeterministicRenderer().render('/etc/ssl/certs/ssl-cert-snakeoil.pem', state)
    assert key_bytes == DeterministicRenderer().render('/etc/ssl/private/ssl-cert-snakeoil.key', state)
