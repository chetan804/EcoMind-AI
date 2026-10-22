"""The Mendeley candidate manifest must fail closed until the files were downloaded and verified."""

from __future__ import annotations

import copy

import pytest

from ml.waste_classification.data import provenance as pv

PATH = pv.REPO / "datasets" / "manifests" / "mendeley-recyclable-1.0.yaml"
MANIFEST = pv.load_manifest(PATH)


def test_the_pending_manifest_is_refused_only_for_the_missing_file_digest() -> None:
    problems = pv.manifest_problems(MANIFEST)
    assert problems == ["images.files_digest must be a SHA-256 hex digest"]
    with pytest.raises(pv.ProvenanceError):
        pv.require_acceptable(MANIFEST)
    assert pv.release_allowed(MANIFEST) is False


def test_the_licence_evidence_is_recorded_and_release_stays_blocked() -> None:
    assert MANIFEST["licence"]["declared"][0]["spdx"] == "CC-BY-4.0"
    assert MANIFEST["licence"]["release_allowed"] is False
    assert MANIFEST["licence"]["open_questions"]
    assert MANIFEST["source"]["downloaded"] is False


def test_with_a_digest_it_would_pass_but_still_not_be_releasable() -> None:
    filled = copy.deepcopy(MANIFEST)
    filled["images"]["files_digest"] = "a" * 64
    pv.require_acceptable(filled)
    assert pv.release_allowed(filled) is False


def test_the_five_classes_map_to_known_materials_and_nothing_is_catch_all() -> None:
    mapping = pv.label_map(MANIFEST)
    assert mapping == {
        c.capitalize(): c for c in ("cardboard", "glass", "metal", "paper", "plastic")
    }


def test_it_is_a_separate_manifest_and_realwaste_is_untouched() -> None:
    realwaste = pv.load_manifest(pv.REPO / "datasets" / "manifests" / "realwaste-2.0.yaml")
    assert realwaste["name"] == "realwaste" and MANIFEST["name"] == "mendeley-recyclable"
    pv.require_acceptable(realwaste)


def test_a_manifest_claiming_to_contain_trashnet_images_is_still_refused() -> None:
    tainted = copy.deepcopy(MANIFEST)
    tainted["images"]["files_digest"] = "b" * 64
    tainted["contains_third_party_from"] = ["TrashNet"]
    with pytest.raises(pv.ProvenanceError, match="prohibited"):
        pv.require_acceptable(tainted)
