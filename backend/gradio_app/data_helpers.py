import gradio as gr
from database.repositories.communes_repo import liste_communes
from database.repositories.departement_repo import liste_departements
from database.repositories.document_repo import liste_documents
from database.repositories.page_repo import get_doc_page, liste_pages_document
from database.repositories.reconnaissance_repo import liste_reconnaissances
from database.repositories.region_repo import liste_regions
from infra.database import Database


async def load_communes(database: Database, departement_id: str | None) -> list[str]:
    async with database.get_session() as session:
        communes = await liste_communes(session, departement_id)
        mapping = [(c.nom, str(c.id)) for c in communes]
        return gr.update(
            choices=mapping,
        )


async def load_departements(database: Database, region_id: str | None):
    async with database.get_session() as session:
        departements = await liste_departements(session, region_id)
        mapping = [(d.nom, str(d.id)) for d in departements]
        return gr.update(
            choices=mapping,
        )


async def load_regions(database: Database):
    async with database.get_session() as session:
        regions = await liste_regions(session)
        mapping = [(r.nom, str(r.id)) for r in regions]
        return gr.update(
            choices=mapping,
        )


async def load_documents(
    database: Database,
    region_id: str | None,
    departement_id: str | None,
    commune_id: str | None,
):
    async with database.get_session() as session:
        documents = await liste_documents(
            session, region_id, departement_id, commune_id
        )
        mapping = [
            [
                d.chemin,
                d.type_document,
                d.mode_document,
                d.code_postal,
                d.nb_pages,
                f"{d.taille_fichier / 1024 / 1024:.2f}",
                d.id,
            ]
            for d in documents
        ]
        return gr.update(value=mapping)


async def load_pages(database: Database, docs, evt: gr.SelectData):
    # selected_row = evt.index[0]
    doc_id = evt.row_value[6]
    async with database.get_session() as session:
        pages = await liste_pages_document(session, doc_id)
        mapping = [[p.num_page, p.texte_brut, p.texte_reconnu, p.id] for p in pages]
        return gr.update(value=mapping)


async def load_document_page(database: Database, doc_id: str, page_number: int):
    async with database.get_session() as session:
        page = await get_doc_page(session, doc_id, page_number)
        return page


async def load_traitements_reconnaissance(database: Database, page_id: str):
    async with database.get_session() as session:
        traitements = await liste_reconnaissances(session, page_id)
        mapping = [
            [t.methode.name, t.score, t.resultat, t.commentaire_traitement]
            for t in traitements
        ]
        return mapping
