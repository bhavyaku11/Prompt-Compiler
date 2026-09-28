# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for Prompt Compiler standalone FastAPI backend."""

import os
import sys

# Locate sqlite_vec extension library
import sqlite_vec
sqlite_vec_dir = os.path.dirname(sqlite_vec.__file__)
vec0_dylib = os.path.join(sqlite_vec_dir, "vec0.dylib")

binaries = []
datas = []
if os.path.exists(vec0_dylib):
    # Include in both binaries and datas so SQLite's load_extension finds vec0 in frozen bundle
    binaries.append((vec0_dylib, "sqlite_vec"))
    datas.append((vec0_dylib, "sqlite_vec"))

hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "anyio._backends._asyncio",
    "sqlean",
    "sqlite_vec",
    "clerk_backend_api",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.pysqlite",
    "pydantic",
    "pydantic_core",
    "starlette",
    "fastapi",
    "httpx",
    "httpcore",
    "h11",
    "cryptography",
    "app.config",
    "app.main",
    "app.runtime",
    "app.auth",
    "app.api.health",
    "app.api.runtime",
    "app.api.auth",
    "app.api.compile",
    "app.api.interview",
    "app.api.projects",
    "app.api.knowledge",
    "app.database.base",
    "app.database.models",
    "app.database.session",
    "app.database.repositories",
    "app.engine.requirements",
    "app.engine.generator",
    "app.engine.critic",
    "app.engine.refiner",
    "app.engine.interviewer",
    "app.engine.project_memory",
    "app.engine.memory_extractor",
    "app.engine.agent_formatter",
    "app.engine.chunker",
    "app.engine.knowledge_indexer",
    "app.engine.knowledge_search",
    "app.engine.knowledge_retrieval",
    "app.engine.document_ingestion",
    "app.templates.agent_presets",
    "app.templates.selector",
    "app.templates.definitions",
    "app.templates.base",
]

excludes = [
    "tests",
    "unittest",
    "pytest",
    "tkinter",
    "test",
    "distutils",
    "pip",
    "setuptools",
]

a = Analysis(
    ["app/desktop_entry.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="prompt-compiler-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
