from pathlib import Path

import gradio as gr
from infra.database import Database

from gradio_app.data_helpers import (
    load_communes,
    load_departements,
    load_document_page,
    load_documents,
    load_regions,
    load_traitements_reconnaissance,
)


def render_pdf_at_page(file_path, page_number):
    if file_path:
        html = f"""
        <iframe src="/gradio_api/file={file_path}#page={page_number}"
                width="100%" height="800px" style="border:none;">
        </iframe>
        """
        return html


async def load_pdf(database: Database, pdf_path: Path, evt: gr.SelectData):
    doc_name = evt.row_value[0]
    if pdf_path and doc_name:
        doc_path = Path(pdf_path) / doc_name
        nb_pages = evt.row_value[4]
        doc = {"doc_path": doc_path, "nb_pages": nb_pages, "doc_id": evt.row_value[6]}
        page = await load_document_page(database, doc["doc_id"], 1)
        traitements = await load_traitements_reconnaissance(database, page.id)
        return (
            render_pdf_at_page(doc_path, 1),
            doc_name,
            gr.update(minimum=1, maximum=nb_pages, value=1),
            doc,
            page.texte_brut,
            page.texte_reconnu,
            traitements,
        )


async def go_to_page(database: Database, doc, page_number):
    page = await load_document_page(database, doc["doc_id"], page_number)
    traitements = await load_traitements_reconnaissance(database, page.id)
    return (
        render_pdf_at_page(doc["doc_path"], page_number),
        page.texte_brut,
        page.texte_reconnu,
        traitements,
    )


def render(database_state: gr.State, pdf_path: gr.State):
    """Construit la page de consultation des fichiers PDF par commune."""
    with gr.Blocks() as view:
        current_pdf = gr.State(None)

        with gr.Row():
            with gr.Column(scale=0.5) as col:
                region = gr.Dropdown(
                    label="Region", choices=[], interactive=True, filterable=True
                )
                departement = gr.Dropdown(
                    label="Département", choices=[], interactive=True, filterable=True
                )
                commune = gr.Dropdown(
                    label="Commune",
                    interactive=True,
                    filterable=True,
                )
                view.load(fn=load_regions, inputs=database_state, outputs=region)
                region.change(
                    fn=load_departements,
                    inputs=[database_state, region],
                    outputs=departement,
                )
                departement.change(
                    fn=load_communes,
                    inputs=[database_state, departement],
                    outputs=commune,
                )

            with gr.Column(scale=2):
                liste_documents = gr.Dataframe(
                    label="Liste des fichiers",
                    headers=[
                        "Nom",
                        "Type",
                        "Mode",
                        "Code postal",
                        "Nb de pages",
                        "Taille (Mo)",
                        "Id document",
                    ],
                    datatype=["str", "str", "str", "str", "int", "int", "str"],
                )
                commune.change(
                    fn=load_documents,
                    inputs=[database_state, region, departement, commune],
                    outputs=liste_documents,
                )
                with gr.Column():
                    nom_doc = gr.Textbox(label="Nom fichier")
                    with gr.Row():
                        slider = gr.Slider(
                            label="Page",
                            minimum=1,
                            maximum=100,
                            step=1,
                            interactive=True,
                        )
                    with gr.Row():
                        page_texte_brut = gr.TextArea(label="Texte brut", lines=10)
                        page_texte_retenu = gr.TextArea(label="Texte retenu", lines=10)
                    with gr.Row():
                        liste_traitements_reconnaissance = gr.DataFrame(
                            label="Liste des traitements",
                            headers=["Méthode", "Score", "Resultat", "Commentaire"],
                        )

            with gr.Column(scale=1):
                pdf_display = gr.HTML()
            liste_documents.select(
                fn=load_pdf,
                inputs=[database_state, pdf_path],
                outputs=[
                    pdf_display,
                    nom_doc,
                    slider,
                    current_pdf,
                    page_texte_brut,
                    page_texte_retenu,
                    liste_traitements_reconnaissance,
                ],
            )
            slider.change(
                fn=go_to_page,
                inputs=[database_state, current_pdf, slider],
                outputs=[
                    pdf_display,
                    page_texte_brut,
                    page_texte_retenu,
                    liste_traitements_reconnaissance,
                ],
            )
    return view
