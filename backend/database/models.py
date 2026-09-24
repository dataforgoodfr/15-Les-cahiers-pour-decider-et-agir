import enum
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID as UUID_Type

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid_extensions import uuid7


@dataclass
class Base(AsyncAttrs, DeclarativeBase):
    pass


class Region(Base):
    __tablename__ = "region"

    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(nullable=False)
    departements: Mapped[list["Departement"]] = relationship(back_populates="region")


class Departement(Base):
    __tablename__ = "departement"

    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    code: Mapped[str] = mapped_column(unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(nullable=False)
    region_id: Mapped[UUID_Type] = mapped_column(ForeignKey("region.id"))
    region: Mapped[Region] = relationship(back_populates="departements")
    communes: Mapped[list["Commune"]] = relationship(back_populates="departement")


class Commune(Base):
    __tablename__ = "commune"

    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    code_insee: Mapped[str] = mapped_column(unique=True, nullable=False)
    codes_postaux: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=True)
    population: Mapped[int] = mapped_column(nullable=True)
    nom: Mapped[str] = mapped_column(nullable=False)
    centre_latitude: Mapped[float] = mapped_column(nullable=True)
    centre_longitude: Mapped[float] = mapped_column(nullable=True)
    departement_id: Mapped[UUID_Type] = mapped_column(ForeignKey("departement.id"))
    departement: Mapped[Departement] = relationship(back_populates="communes")


class TypeDocument(enum.Enum):
    """Type de document."""

    CC = "Cahier citoyen"
    CO = "Contribution individuelle"
    CR = "Compte rendu de réunion d'initiative locale"
    IL = "Comptes rendus envoyés en pièce jointe de messages électroniques"


class ModeDocument(enum.Enum):
    """Mode de document."""

    M = "Manuscrit"
    D = "Dactylographié"
    MD = "Manuscrit et dactylographié"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    chemin: Mapped[str] = mapped_column(unique=True, nullable=False)
    nom: Mapped[str] = mapped_column(nullable=False)
    type_document: Mapped[TypeDocument] = mapped_column(nullable=False)
    mode_document: Mapped[ModeDocument] = mapped_column(nullable=False)
    code_postal: Mapped[str] = mapped_column(nullable=True)
    taille_fichier: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    commune_id: Mapped[UUID_Type] = mapped_column(ForeignKey("commune.id"))
    commune: Mapped[Commune] = relationship()


class Page(Base):
    __tablename__ = "page"

    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    num_page: Mapped[int] = mapped_column()
    texte_brut: Mapped[str] = mapped_column()
    texte_reconnu: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    document_id: Mapped[UUID_Type] = mapped_column(ForeignKey("document.id"))
    document: Mapped[Document] = relationship()


class MethodeReconnaissance(enum.Enum):
    PDF_TEXT = "Extraction du texte depuis les meta-données PDF"


class Reconnaissance(Base):
    __tablename__ = "reconnaissance"
    id: Mapped[UUID_Type] = mapped_column(primary_key=True, insert_default=uuid7)
    methode: Mapped[MethodeReconnaissance] = mapped_column(nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    resultat: Mapped[str] = mapped_column(nullable=True)
    commentaire_traitement: Mapped[str] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    page_id: Mapped[UUID_Type] = mapped_column(ForeignKey("page.id"))
    page: Mapped[Page] = relationship()
