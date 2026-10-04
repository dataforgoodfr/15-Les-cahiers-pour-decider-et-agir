import logging
from pathlib import Path

import gradio as gr

# from data_helpers import PDF_DIR
from infra.container import Container

from gradio_app.views import navigation_pdf

container = Container()
container.logging()

logger = logging.getLogger(__name__)

STYLE = Path(__file__).parent / "views" / "style.css"


async def get_session():
    """Get a database connection from the container."""
    return container.database()


def get_settings():
    return container.settings().pdf_data_dir


async def close_session(session):
    """Close a database session."""
    if session:
        await session.close()


# VUE COMMUNES
with gr.Blocks(title="Cahiers de doléances", fill_width=True) as demo:
    database = gr.State(None)
    pdf_path = gr.State(None)
    demo.load(fn=get_session, outputs=[database])
    demo.load(fn=get_settings, outputs=[pdf_path])
    # barre de navigation : la vue graphe est une page à part (voir le docstring),
    # on y accède par un lien plutôt que par un onglet
    gr.HTML('<div class="nav"><h1>Visualisation des contributions</h1></div>')

    navigation_pdf.render(database, pdf_path)


# VUE GRAPH DE TOPIC
app = gr.Server()
# no-store : recharger la page reprend les fichiers static/ à jour
_NO_STORE = {"Cache-Control": "no-store"}


# le Blocks est monté en dernier : sa route "/" ne doit pas masquer /graphe
gr.mount_gradio_app(
    app,
    demo,
    path="/",
    allowed_paths=[str(container.settings().pdf_data_dir)],
    auth=(container.settings().gradio_user, container.settings().gradio_password),
)


if __name__ == "__main__":
    app.launch()
