import asyncio
import logging

import aiohttp
from database.models import Region
from database.repositories.communes_repo import create_commune
from database.repositories.departement_repo import create_departement
from database.repositories.region_repo import create_region
from infra.container import Container
from tqdm import tqdm

API_GET_REGION = "https://geo.api.gouv.fr/regions"
API_GET_DEPARTEMENT = "https://geo.api.gouv.fr/regions/{code}/departements"
API_GET_COMMUNE = "https://geo.api.gouv.fr/departements/{code}/communes?fields=centre,population,codesPostaux"

container = Container()
container.logging()

logger = logging.getLogger(__name__)


async def chargement_regions(db_session):
    async with aiohttp.ClientSession() as client:
        response = await client.get(API_GET_REGION)
        if response.status != 200:
            logger.error(
                f"Echec de l'appel à l'API découpage administratif: {response.status}"
            )
            await db_session.rollback()
            return
        response_json = await response.json()
        for r in tqdm(response_json, "Chargement des régions"):
            code = r.get("code")
            nom = r.get("nom")
            yield create_region(db_session, code, nom)


async def chargement_departements(db_session, region: Region):
    async with aiohttp.ClientSession() as client:
        response = await client.get(API_GET_DEPARTEMENT.format(code=region.code))
        if response.status != 200:
            logger.error(
                f"Echec de l'appel à l'API découpage administratif: {response.status}"
            )
            await db_session.rollback()
            return
        response_json = await response.json()
        for d in tqdm(response_json, f"Chargement des départements {region.nom}"):
            code = d.get("code")
            nom = d.get("nom")
            yield create_departement(db_session, region, code, nom)


async def chargement_communes(db_session, departement):
    async with aiohttp.ClientSession() as client:
        response = await client.get(API_GET_COMMUNE.format(code=departement.code))
        if response.status != 200:
            logger.error(
                f"Echec de l'appel à l'API découpage administratif: {response.status}"
            )
            await db_session.rollback()
            return
        response_json = await response.json()
        for c in tqdm(response_json, f"Chargement des communes {departement.nom}"):
            centre = c.get("centre", {}).get("coordinates", [None, None])
            create_commune(
                db_session,
                departement,
                c.get("code"),
                c.get("nom"),
                c.get("codesPostaux"),
                c.get("population"),
                centre[0],
                centre[1],
            )


async def main():
    async with (
        container.database().get_session() as db_session,
        db_session.begin(),
    ):
        coros = []
        async for region in chargement_regions(db_session):
            async for departement in chargement_departements(db_session, region):
                coros.append(chargement_communes(db_session, departement))
        await asyncio.gather(*coros)
        r_1 = create_region(db_session, "-1", "Etranger ou inconnu")
        d_1 = create_departement(db_session, r_1, "-1", "Etranger ou inconnu")
        create_commune(db_session, d_1, "-1", "Etranger ou inconnu")

        await db_session.commit()


asyncio.run(main())
