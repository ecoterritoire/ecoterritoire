import os
from io import BytesIO
from datetime import date, timedelta

import pandas as pd
import requests
from tqdm import tqdm
from multiprocessing import Pool

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions


# ============================================================
# Configuration
# ============================================================

BASE_URL = (
    "https://files.data.gouv.fr/ineris/lcsqa/"
    "concentrations-de-polluants-atmospheriques-reglementes/"
    "temps-reel"
)

# Années à importer
ANNEES = [2021, 2022, 2023, 2024, 2025, 2026]

# Nombre de processus utilisés pour télécharger / traiter
NB_PROCESSUS = os.cpu_count()

# InfluxDB
INFLUXDB_URL = os.getenv(
    "INFLUXDB_URL",
    "http://localhost:8086"
)

INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")

INFLUXDB_ORG = os.getenv(
    "INFLUXDB_ORG",
    "mon-org"
)

INFLUXDB_BUCKET = os.getenv(
    "INFLUXDB_BUCKET",
    "qualite-air"
)

MEASUREMENT = "pollution_air"


# ============================================================
# Colonnes InfluxDB
# ============================================================

TAG_COLUMNS = [
    "Organisme",
    "code zas",
    "Zas",
    "code site",
    "nom site",
    "type d'implantation",
    "Polluant",
    "type d'influence",
    "discriminant",
    "Réglementaire",
    "type d'évaluation",
    "procédure de mesure",
    "type de valeur",
    "unité de mesure",
]


# ============================================================
# Génération des dates
# ============================================================

def generer_dates():
    """
    Génère toutes les dates des années demandées.

    Pour 2026, on s'arrête à aujourd'hui.
    """

    dates = []

    aujourd_hui = date.today()

    for annee in ANNEES:

        debut = date(annee, 1, 1)

        # Fin normale de l'année
        fin = date(annee, 12, 31)

        # Pour l'année actuelle :
        # on ne va pas dans le futur
        if annee == aujourd_hui.year:
            fin = aujourd_hui

        # Si l'année est dans le futur, on l'ignore
        if debut > aujourd_hui:
            continue

        date_courante = debut

        while date_courante <= fin:
            dates.append(date_courante)
            date_courante += timedelta(days=1)

    return dates


# ============================================================
# Traitement d'une journée
# ============================================================

def traiter_jour(date_courante):

    date_str = date_courante.strftime("%Y-%m-%d")
    annee = date_courante.year

    url = (
        f"{BASE_URL}/{annee}/"
        f"FR_E2_{date_str}.csv"
    )

    try:

        response = requests.get(
            url,
            timeout=120
        )

        # Certains jours peuvent ne pas avoir de fichier
        if response.status_code == 404:
            return {
                "date": date_courante,
                "data": None,
                "erreur": None,
                "disponible": False,
            }

        response.raise_for_status()

        df = pd.read_csv(
            BytesIO(response.content),
            sep=";",
            decimal=".",
            encoding="utf-8",
        )

        # ----------------------------------------------------
        # Conversion des données
        # ----------------------------------------------------

        df["Date de début"] = pd.to_datetime(
            df["Date de début"],
            format="%Y/%m/%d %H:%M:%S",
            errors="coerce",
        )

        df["valeur"] = pd.to_numeric(
            df["valeur"],
            errors="coerce",
        )

        df["date"] = df["Date de début"].dt.date

        # ----------------------------------------------------
        # Agrégation quotidienne
        # ----------------------------------------------------

        GROUP_COLUMNS = [
            "date",
            "Organisme",
            "code zas",
            "Zas",
            "code site",
            "nom site",
            "type d'implantation",
            "Polluant",
            "type d'influence",
            "discriminant",
            "Réglementaire",
            "type d'évaluation",
            "procédure de mesure",
            "type de valeur",
            "unité de mesure",
        ]

        df = (
            df.groupby(
                GROUP_COLUMNS,
                dropna=False
            )
            .agg(
                moyenne=("valeur", "mean"),
                minimum=("valeur", "min"),
                maximum=("valeur", "max"),
                nombre_mesures=("valeur", "count"),
            )
            .reset_index()
        )

        # ----------------------------------------------------
        # Arrondi
        # ----------------------------------------------------

        df["moyenne"] = df["moyenne"].round(3)
        df["minimum"] = df["minimum"].round(3)
        df["maximum"] = df["maximum"].round(3)

        return {
            "date": date_courante,
            "data": df,
            "erreur": None,
            "disponible": True,
        }

    except Exception as e:

        return {
            "date": date_courante,
            "data": None,
            "erreur": str(e),
            "disponible": False,
        }


# ============================================================
# DataFrame -> Points InfluxDB
# ============================================================

def dataframe_to_points(df):

    points = []

    for _, row in df.iterrows():

        point = Point(MEASUREMENT)

        # ----------------------------------------------------
        # Tags
        # ----------------------------------------------------

        for column in TAG_COLUMNS:

            value = row[column]

            if pd.notna(value):
                point.tag(
                    column,
                    str(value)
                )

        # ----------------------------------------------------
        # Fields
        # ----------------------------------------------------

        if pd.notna(row["moyenne"]):
            point.field(
                "moyenne",
                float(row["moyenne"])
            )

        if pd.notna(row["minimum"]):
            point.field(
                "minimum",
                float(row["minimum"])
            )

        if pd.notna(row["maximum"]):
            point.field(
                "maximum",
                float(row["maximum"])
            )

        if pd.notna(row["nombre_mesures"]):
            point.field(
                "nombre_mesures",
                int(row["nombre_mesures"])
            )

        # ----------------------------------------------------
        # Timestamp
        # ----------------------------------------------------

        timestamp = (
            pd.Timestamp(row["date"])
            .tz_localize("UTC")
        )

        point.time(
            timestamp.to_pydatetime(),
            WritePrecision.S
        )

        points.append(point)

    return points


# ============================================================
# Programme principal
# ============================================================

def main():

    if not INFLUXDB_TOKEN:
        raise RuntimeError(
            "La variable d'environnement "
            "INFLUXDB_TOKEN n'est pas définie."
        )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    dates = generer_dates()

    print()
    print("========================================")
    print("Import des données de qualité de l'air")
    print("========================================")
    print()
    print(f"Années : {ANNEES}")
    print(f"Nombre de jours à vérifier : {len(dates)}")
    print(f"Processus : {NB_PROCESSUS}")
    print()

    # --------------------------------------------------------
    # Connexion InfluxDB
    # --------------------------------------------------------

    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
    )

    # --------------------------------------------------------
    # Écriture ASYNCHRONE
    #
    # Les points sont accumulés puis envoyés par lots.
    # --------------------------------------------------------

    write_api = client.write_api(
        write_options=WriteOptions(
            batch_size=5000,
            flush_interval=1000,
            jitter_interval=0,
            retry_interval=5000,
            max_retries=5,
        )
    )

    # --------------------------------------------------------
    # Téléchargement + traitement parallèle
    # --------------------------------------------------------

    resultats = []

    with Pool(
        processes=NB_PROCESSUS
    ) as pool:

        for resultat in tqdm(
            pool.imap_unordered(
                traiter_jour,
                dates
            ),
            total=len(dates),
            desc="Téléchargement / traitement",
        ):

            resultats.append(resultat)

    # --------------------------------------------------------
    # Tri chronologique
    # --------------------------------------------------------

    resultats.sort(
        key=lambda resultat: resultat["date"]
    )

    # --------------------------------------------------------
    # Import InfluxDB
    # --------------------------------------------------------

    total_points = 0
    jours_disponibles = 0
    jours_absents = 0
    erreurs = []

    print()
    print("Import dans InfluxDB...")

    for resultat in tqdm(
        resultats,
        desc="Import InfluxDB",
    ):

        # Fichier absent
        if not resultat["disponible"]:

            if resultat["erreur"] is None:
                jours_absents += 1

            else:
                erreurs.append(
                    (
                        resultat["date"],
                        resultat["erreur"]
                    )
                )

            continue

        jours_disponibles += 1

        df = resultat["data"]

        if df is None or df.empty:
            continue

        points = dataframe_to_points(df)

        if not points:
            continue

        # ----------------------------------------------------
        # Écriture asynchrone
        # ----------------------------------------------------

        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=points,
        )

        total_points += len(points)

    # --------------------------------------------------------
    # Attendre que tous les lots soient réellement envoyés
    # --------------------------------------------------------

    print()
    print("Attente de la fin des écritures InfluxDB...")

    write_api.flush()

    write_api.close()
    client.close()

    # --------------------------------------------------------
    # Résumé
    # --------------------------------------------------------

    print()
    print("========================================")
    print("Import terminé")
    print("========================================")
    print()
    print(f"Jours demandés      : {len(dates)}")
    print(f"Jours disponibles   : {jours_disponibles}")
    print(f"Jours absents       : {jours_absents}")
    print(f"Points envoyés      : {total_points}")

    if erreurs:

        print()
        print(
            f"Jours en erreur : {len(erreurs)}"
        )

        for date_erreur, message in erreurs:

            print(
                f"  {date_erreur} : {message}"
            )


if __name__ == "__main__":
    main()