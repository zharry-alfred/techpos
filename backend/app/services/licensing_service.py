import base64
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
from app.utils.hardware_fingerprint import get_hardware_fingerprint

class LicensingService:
    @staticmethod
    def ensure_keys_exist(keys_dir: Path):
        """Ensure asymmetric Ed25519 key pair exists for platform licensing."""
        keys_dir.mkdir(parents=True, exist_ok=True)
        priv_path = keys_dir / "license_private_ed25519.pem"
        pub_path = keys_dir / "license_public_ed25519.pem"

        if not priv_path.exists() or not pub_path.exists():
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Save private key (Super Admin only in production)
            with open(priv_path, "wb") as f:
                f.write(
                    private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    )
                )

            # Save public key (Embedded in POS offline binaries)
            with open(pub_path, "wb") as f:
                f.write(
                    public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo
                    )
                )

    @classmethod
    def load_private_key(cls, key_path: str) -> ed25519.Ed25519PrivateKey:
        path = Path(key_path)
        if not path.exists():
            cls.ensure_keys_exist(path.parent)
        with open(path, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    @classmethod
    def load_public_key(cls, key_path: str) -> ed25519.Ed25519PublicKey:
        path = Path(key_path)
        if not path.exists():
            cls.ensure_keys_exist(path.parent)
        with open(path, "rb") as f:
            return serialization.load_pem_public_key(f.read())

    @classmethod
    def issue_license(
        cls,
        store_id: str,
        store_code: str,
        hardware_fingerprint: str,
        private_key_path: str,
        days_valid: int = 365,
        tier: str = "ENTERPRISE",
        allowed_modules: list = None,
        max_terminals: int = 10
    ) -> dict:
        """Issue a digitally signed license certificate (.lic) binding store & hardware."""
        if allowed_modules is None:
            allowed_modules = ["RETAIL", "FOOD_BEVERAGE", "INVENTORY", "KDS", "CFD", "OFFLINE_SYNC"]

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=days_valid)

        payload = {
            "v": "6.0",
            "store_id": str(store_id),
            "store_code": store_code,
            "hardware_fingerprint": hardware_fingerprint,
            "tier": tier,
            "allowed_modules": allowed_modules,
            "max_terminals": max_terminals,
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Canonical json string for deterministic signing
        canonical_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
        
        priv_key = cls.load_private_key(private_key_path)
        signature = priv_key.sign(canonical_bytes)
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        certificate = {
            "payload": payload,
            "signature": signature_b64
        }
        
        # Also provide a compact base64-encoded single-string key
        raw_cert_json = json.dumps(certificate)
        compact_key = base64.b64encode(raw_cert_json.encode('utf-8')).decode('utf-8')

        return {
            "certificate": certificate,
            "license_key": compact_key,
            "expires_at": expires_at.isoformat()
        }

    @classmethod
    def verify_license(
        cls,
        license_data: str | dict,
        public_key_path: str,
        expected_store_id: str = None,
        enforce_hardware: bool = True
    ) -> dict:
        """Verify license signature and validity against host machine without network calls."""
        try:
            if isinstance(license_data, str):
                # Try decoding as compact base64, else parse as json
                try:
                    decoded_str = base64.b64decode(license_data).decode('utf-8')
                    cert = json.loads(decoded_str)
                except Exception:
                    cert = json.loads(license_data)
            else:
                cert = license_data

            payload = cert.get("payload")
            signature_b64 = cert.get("signature")

            if not payload or not signature_b64:
                return {"valid": False, "error": "Malformed license certificate structure"}

            # Verify cryptographic signature
            canonical_bytes = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode('utf-8')
            signature = base64.b64decode(signature_b64)
            pub_key = cls.load_public_key(public_key_path)

            try:
                pub_key.verify(signature, canonical_bytes)
            except InvalidSignature:
                return {"valid": False, "error": "Invalid cryptographic signature. Tampering detected."}

            # Check expiration date
            expires_at = datetime.fromisoformat(payload.get("expires_at"))
            now = datetime.now(timezone.utc)
            if now > expires_at:
                return {"valid": False, "error": f"License expired on {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"}

            # Check store_id if provided
            if expected_store_id and str(payload.get("store_id")) != str(expected_store_id):
                return {"valid": False, "error": "License is registered to a different store"}

            # Check hardware fingerprint binding
            if enforce_hardware:
                license_hw = payload.get("hardware_fingerprint")
                if license_hw and license_hw != "*":
                    current_hw = get_hardware_fingerprint()
                    if license_hw != current_hw:
                        return {
                            "valid": False,
                            "error": f"Hardware fingerprint mismatch. Licensed for {license_hw}, running on {current_hw}"
                        }

            return {
                "valid": True,
                "payload": payload,
                "expires_at": expires_at
            }
        except Exception as e:
            return {"valid": False, "error": f"License validation exception: {str(e)}"}
