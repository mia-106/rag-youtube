[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "rag-youtube"
version = "0.1.0"
description = "YouTube Agentic RAG System"
requires-python = ">=3.12"
dependencies = []

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]
