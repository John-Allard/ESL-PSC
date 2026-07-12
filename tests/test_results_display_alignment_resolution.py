from __future__ import annotations

import pytest

from gui.ui.widgets.results_display import _get_alignment_length, _resolve_alignment_path


@pytest.mark.parametrize("extension", [".fas", ".fasta", ".fa", ".faa"])
def test_resolve_alignment_path_accepts_supported_fasta_extensions(tmp_path, extension):
    path = tmp_path / f"A2M{extension}"
    path.write_text(">sp1\nAAAA\n", encoding="utf-8")

    assert _resolve_alignment_path("A2M", str(tmp_path)) == str(path)


def test_resolve_alignment_path_accepts_gene_name_with_extension(tmp_path):
    path = tmp_path / "A2M.fa"
    path.write_text(">sp1\nAAAA\n", encoding="utf-8")

    assert _resolve_alignment_path("A2M.fa", str(tmp_path)) == str(path)


def test_resolve_alignment_path_falls_back_case_insensitively(tmp_path):
    path = tmp_path / "A2M.FA"
    path.write_text(">sp1\nAAAA\n", encoding="utf-8")

    assert _resolve_alignment_path("a2m", str(tmp_path)) == str(path)


def test_get_alignment_length_uses_supported_fasta_extensions(tmp_path):
    path = tmp_path / "A2M.fa"
    path.write_text(">sp1\nAAAAAA\n", encoding="utf-8")

    assert _get_alignment_length("A2M", str(tmp_path)) == 6


def test_resolve_alignment_path_error_lists_supported_extensions(tmp_path):
    with pytest.raises(FileNotFoundError) as excinfo:
        _resolve_alignment_path("A2M", str(tmp_path))

    message = str(excinfo.value)
    assert "A2M" in message
    assert ".fas" in message
    assert ".fasta" in message
    assert ".fa" in message
    assert ".faa" in message
