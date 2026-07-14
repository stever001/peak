"""Controlled engagement database layer (MySQL via SQLAlchemy).

Defines the declarative Base, governance/audit mixins, Python enum contracts, and the
ORM models for the controlled database. This is a **local scaffold** (Phase 11): schema
definitions only, no data, no production deployment. Credentials come from the
environment (see peak/db/session.py and .env.example), never from the repo.
"""
