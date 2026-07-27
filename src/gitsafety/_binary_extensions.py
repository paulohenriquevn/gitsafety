"""Extensões tratadas como binárias (ADR D1).

Notas de manutenção — mesma disciplina do
`ggshield/ggshield/utils/_binary_extensions.py`:

- mantenha o conjunto **ordenado**, para que o diff de uma adição seja legível;
- extensões sem o ponto inicial;
- em minúsculas — a comparação normaliza o sufixo antes de consultar.

Este é um módulo de **dados**, separado da lógica de propósito: 200+ strings dentro
de `walker.py` afogariam a heurística que realmente importa.

O custo de cada entrada aqui é um falso negativo em potencial (arquivo de texto com
essa extensão nunca é varrido). Só adicione formato que seja binário de fato.
"""
from __future__ import annotations

BINARY_EXTENSIONS: frozenset[str] = frozenset(
    {
        # Arquivos compactados
        "7z", "br", "bz2", "cab", "gz", "lz", "lzma", "rar", "tar", "tgz",
        "xz", "z", "zip", "zst",
        # Áudio
        "aac", "flac", "m4a", "mid", "midi", "mp3", "oga", "ogg", "opus",
        "wav", "wma",
        # Documentos binários
        "doc", "docx", "odp", "ods", "odt", "pdf", "ppt", "pptx", "rtf",
        "xls", "xlsb", "xlsx",
        # Executáveis e bibliotecas
        "a", "app", "bin", "class", "com", "dll", "dylib", "elf", "exe",
        "jar", "ko", "lib", "msi", "o", "obj", "pdb", "pyc", "pyd", "pyo",
        "so", "wasm",
        # Fontes
        "eot", "otf", "ttc", "ttf", "woff", "woff2",
        # Imagens
        "avif", "bmp", "gif", "heic", "heif", "ico", "icns", "jpeg", "jpg",
        "png", "psd", "svgz", "tif", "tiff", "webp",
        # Imagens de disco e pacotes
        "deb", "dmg", "img", "iso", "pkg", "rpm", "vmdk",
        # Modelos e dados binários de ML — relevantes para o público de dados
        "arrow", "feather", "h5", "hdf5", "joblib", "npy", "npz", "onnx",
        "parquet", "pb", "pickle", "pkl", "pt", "pth", "safetensors", "tflite",
        # Bancos de dados embarcados
        "db", "mdb", "sqlite", "sqlite3",
        # Vídeo
        "avi", "flv", "m4v", "mkv", "mov", "mp4", "mpeg", "mpg", "webm", "wmv",
    }
)
