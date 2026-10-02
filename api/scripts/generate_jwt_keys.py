"""Print an RS256 key pair formatted for .env (newlines escaped as \\n)."""

from app.core.security import generate_rsa_key_pair


def main() -> None:
    private_pem, public_pem = generate_rsa_key_pair()
    print("JWT_PRIVATE_KEY=" + private_pem.strip().replace("\n", "\\n"))
    print("JWT_PUBLIC_KEY=" + public_pem.strip().replace("\n", "\\n"))


if __name__ == "__main__":
    main()
