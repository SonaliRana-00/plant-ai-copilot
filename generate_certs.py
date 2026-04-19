from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import SubjectAlternativeName, DNSName, UniformResourceIdentifier
import datetime
import os

def generate_certificate(name, uri, output_dir="./certs"):
    os.makedirs(output_dir, exist_ok=True)

    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Certificate details
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Plant AI Co-pilot"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        )
        .add_extension(
            SubjectAlternativeName([
                DNSName("localhost"),
                UniformResourceIdentifier(uri),
            ]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )

    # Save certificate
    cert_path = os.path.join(output_dir, f"{name}_cert.pem")
    key_path  = os.path.join(output_dir, f"{name}_key.pem")

    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ))

    print(f"Generated: {cert_path}")
    print(f"Generated: {key_path}")
    return cert_path, key_path

# Generate certificate for app client
generate_certificate(
    name="plant_app",
    uri="urn:plant:ai:copilot"
)

# Generate certificate for PLC server
generate_certificate(
    name="virtual_plc",
    uri="urn:plant:virtual:plc"
)

print("\nAll certificates generated!")
print("Location: ./certs/")