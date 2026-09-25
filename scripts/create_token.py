#!/usr/bin/env python3
"""Script utilitaire pour creer et stocker un nouveau token d'API dans PostgreSQL.

Usage:
    python scripts/create_token.py "Description du token"
"""

import sys
from pathlib import Path

# Ajouter le dossier racine du projet au PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lib.db import DATABASE_URL, generate_new_token, init_db


def main() -> None:
    description = sys.argv[1] if len(sys.argv) > 1 else "Token de developpement"
    print(f"Connexion a PostgreSQL via : {DATABASE_URL}")

    # Initialisation de la table si necessaire
    init_db()

    token, record = generate_new_token(description=description)

    print("\n" + "=" * 60)
    print("TOKEN GENERE AVEC SUCCES")
    print("=" * 60)
    print(f"Token brut (Secret) : {token}")
    print(f"Hash SHA-256 stocke : {record['token_hash']}")
    print(f"Description         : {record['description']}")
    print(f"Date de creation    : {record['created_at']}")
    print("=" * 60)
    print("\nUtilisation avec curl :")
    print(
        f'curl -H "Authorization: Bearer {token}" http://localhost:8000/measurements'
    )
    print("\nAttention: conservez ce token, il n'est pas stocke en clair en base.")


if __name__ == "__main__":
    main()
