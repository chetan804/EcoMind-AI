"""Provenance gate: licence/provenance validation, prohibited-dataset exclusion, leakage, labels."""

from __future__ import annotations

import copy
import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml

from ml.waste_classification.data import provenance as pv
from ml.waste_classification.data.dataset import load_verified
from ml.waste_classification.training import pipeline as pl

REPO = pv.REPO
GOOD = pv.load_manifest(REPO / "datasets" / "manifests" / "realwaste-2.0.yaml")
CONFIG = yaml.safe_load((REPO / "ml" / "configs" / "waste_classification.yaml").read_text())
MANIFESTS = REPO / "datasets" / "manifests"


def variant(**changes: Any) -> dict[str, Any]:
    """The committed RealWaste manifest with overrides; ``a__b`` is the path a.b, None deletes."""
    manifest = copy.deepcopy(GOOD)
    for dotted, value in changes.items():
        *path, leaf = dotted.split("__")
        node = manifest
        for part in path:
            node = node[part]
        if value is None:
            node.pop(leaf, None)
        else:
            node[leaf] = value
    return manifest


# -- the committed manifest ------------------------------------------------------------------------
def test_the_committed_realwaste_manifest_passes_but_is_not_releasable() -> None:
    assert pv.manifest_problems(GOOD) == []
    assert GOOD["licence"]["status"] == "conflicting"
    declared = {d["spdx"] for d in GOOD["licence"]["declared"]}
    assert declared == {"CC-BY-4.0", "CC-BY-NC-SA-4.0"}
    assert pv.release_allowed(GOOD) is False


def test_a_licence_conflict_cannot_be_declared_releasable_without_a_resolution() -> None:
    problems = pv.manifest_problems(variant(licence__release_allowed=True))
    assert any("conflicting" in p for p in problems)


def test_sources_that_disagree_must_say_conflicting() -> None:
    problems = pv.manifest_problems(variant(licence__status="verified"))
    assert any("different licences" in p for p in problems)


def test_a_recorded_resolution_with_evidence_and_date_allows_release() -> None:
    resolved = variant(
        licence__status="resolved",
        licence__release_allowed=True,
        licence__resolution={"evidence": "e-mail from the authors", "date": "2026-11-01"},
    )
    assert pv.manifest_problems(resolved) == []
    assert pv.release_allowed(resolved) is True


# -- fail closed on missing provenance -------------------------------------------------------
@pytest.mark.parametrize(
    "field",
    ["version", "accessed", "source", "licence", "citation", "images", "labels", "split"],
)
def test_a_manifest_missing_any_required_section_is_refused(field: str) -> None:
    manifest = copy.deepcopy(GOOD)
    del manifest[field]
    with pytest.raises(pv.ProvenanceError):
        pv.require_acceptable(manifest)


@pytest.mark.parametrize(
    "overrides",
    [
        {"source__url": ""},
        {"source__version": ""},
        {"citation__text": ""},
        {"accessed": "yesterday"},
        {"images__files_digest": "abc"},
        {"split__seed": None},
    ],
)
def test_blank_or_malformed_provenance_fields_are_refused(overrides: dict[str, Any]) -> None:
    with pytest.raises(pv.ProvenanceError):
        pv.require_acceptable(variant(**overrides))


def test_an_unknown_licence_or_missing_licence_evidence_is_refused() -> None:
    unknown = copy.deepcopy(GOOD)
    unknown["licence"]["declared"] = [{"source": "readme", "spdx": "unknown", "evidence": "none"}]
    assert any("unknown" in p for p in pv.manifest_problems(unknown))
    no_evidence = copy.deepcopy(GOOD)
    del no_evidence["licence"]["declared"][0]["evidence"]
    assert any("evidence" in p for p in pv.manifest_problems(no_evidence))
    assert pv.manifest_problems(variant(licence__declared=[]))


# -- prohibited datasets ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name", ["trashnet", "TrashNet", "trash-net", "TRASH_NET 1.0", "TrashBox", "trashbox-v2"]
)
def test_prohibited_dataset_names_are_refused_however_they_are_spelled(name: str) -> None:
    assert any("prohibited" in p for p in pv.manifest_problems(variant(name=name)))


def test_a_prohibited_source_url_or_declared_third_party_content_is_refused() -> None:
    for changes in (
        {"source__url": "https://github.com/garythung/trashnet"},
        {"source__mirror_url": "https://github.com/x/TrashBox"},
        {"contains_third_party_from": ["TrashNet"]},
    ):
        assert any("prohibited" in p for p in pv.manifest_problems(variant(**changes)))


def test_the_legacy_trashnet_and_trashbox_manifests_are_refused() -> None:
    for name in ("trashnet-1.0", "trashbox-research-1.0"):
        with pytest.raises(pv.ProvenanceError, match="prohibited"):
            pv.require_acceptable(pv.load_manifest(MANIFESTS / f"{name}.yaml"))


def test_the_training_config_points_at_realwaste_and_names_no_prohibited_dataset() -> None:
    dataset = yaml.safe_dump(CONFIG["dataset"]).lower()
    assert "trashnet" not in dataset and "trashbox" not in dataset
    assert CONFIG["dataset"]["manifest"] == "datasets/manifests/realwaste-2.0.yaml"


def test_the_denylist_holds_every_trashnet_digest_and_nothing_malformed() -> None:
    denylist = pv.load_denylist()
    assert len(denylist) == 2524  # distinct digests of the 2,527 TrashNet images (3 exact copies)
    assert all(len(d) == 64 for d in denylist)


def test_a_file_whose_bytes_match_a_prohibited_image_is_found_by_content_not_name() -> None:
    forbidden = "a" * 64
    deny = frozenset({forbidden})
    hashes = {"Glass/Glass_1.jpg": "b" * 64, "Glass/renamed_innocent_name.jpg": forbidden}
    assert pv.prohibited_files(hashes, deny) == ["Glass/renamed_innocent_name.jpg"]
    with pytest.raises(pv.ProvenanceError, match="byte-identical"):
        pv.require_no_prohibited_files(hashes, deny)
    pv.require_no_prohibited_files({"x.jpg": "c" * 64}, deny)


def test_a_missing_empty_or_malformed_denylist_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(pv.ProvenanceError, match="missing"):
        pv.load_denylist(tmp_path / "none.txt")
    (tmp_path / "empty.txt").write_text("# only a comment\n")
    with pytest.raises(pv.ProvenanceError, match="empty"):
        pv.load_denylist(tmp_path / "empty.txt")
    (tmp_path / "bad.txt").write_text("not-a-digest\n")
    with pytest.raises(pv.ProvenanceError, match="malformed"):
        pv.load_denylist(tmp_path / "bad.txt")


def _config_for(tmp_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    (tmp_path / "manifest.yaml").write_text(yaml.safe_dump(manifest))
    (tmp_path / "deny.txt").write_text("a" * 64 + "\n")
    config: dict[str, Any] = copy.deepcopy(CONFIG)
    config["dataset"].update(
        manifest=str(tmp_path / "manifest.yaml"),
        denylist=str(tmp_path / "deny.txt"),
        root=str(tmp_path / "data"),
    )
    return config


def test_the_loader_refuses_a_dataset_directory_that_is_not_fetched(tmp_path: Path) -> None:
    with pytest.raises(pv.ProvenanceError, match="missing"):
        load_verified(_config_for(tmp_path, GOOD))


def test_the_loader_checks_provenance_before_touching_the_images(tmp_path: Path) -> None:
    config = _config_for(tmp_path, variant(name="trashnet"))
    with pytest.raises(pv.ProvenanceError, match="prohibited"):
        load_verified(config)  # refused although the data directory does not even exist


def test_the_loader_refuses_content_that_differs_from_the_pinned_digest(tmp_path: Path) -> None:
    config = _config_for(tmp_path, GOOD)
    for folder in pv.label_map(GOOD):
        (tmp_path / "data" / folder).mkdir(parents=True)
        (tmp_path / "data" / folder / f"{folder}_1.jpg").write_bytes(folder.encode())
    with pytest.raises(pv.ProvenanceError, match="count differs"):
        load_verified(config)
    # right count, wrong bytes: the content digest catches it
    right_count = variant(images__total=len(pv.label_map(GOOD)))
    with pytest.raises(pv.ProvenanceError, match="content differs"):
        load_verified(_config_for(tmp_path, right_count))


def test_the_loader_refuses_an_image_that_matches_the_denylist(tmp_path: Path) -> None:
    import hashlib

    manifest = variant(images__total=5)
    config = _config_for(tmp_path, manifest)
    for folder in pv.label_map(GOOD):
        (tmp_path / "data" / folder).mkdir(parents=True)
    forbidden = b"pretend this is a TrashNet photograph"
    (tmp_path / "data" / "Glass" / "Glass_1.jpg").write_bytes(forbidden)
    (tmp_path / "deny.txt").write_text(hashlib.sha256(forbidden).hexdigest() + "\n")
    # at least one file per trained class is needed to list samples
    for folder, target in pv.label_map(GOOD).items():
        if target and folder != "Glass":
            (tmp_path / "data" / folder / f"{folder}_1.jpg").write_bytes(folder.encode())
    with pytest.raises(pv.ProvenanceError, match="byte-identical"):
        load_verified(config)


# -- label mapping ---------------------------------------------------------------------------------
def test_miscellaneous_trash_is_not_a_known_material() -> None:
    labels = pv.label_map(GOOD)
    assert labels["Miscellaneous Trash"] is None
    assert labels["Food Organics"] is None and labels["Textile Trash"] is None
    assert labels["Vegetation"] is None
    trained = {c for c in labels.values() if c is not None}
    assert trained == set(CONFIG["dataset"]["classes"])
    assert trained == {"cardboard", "glass", "metal", "paper", "plastic"}
    assert "trash" not in trained


def test_a_catch_all_label_cannot_be_mapped_to_a_material_without_justification() -> None:
    manifest = copy.deepcopy(GOOD)
    entry = next(e for e in manifest["labels"]["classes"] if e["name"] == "Miscellaneous Trash")
    entry["maps_to"] = "plastic"
    assert any("catch-all" in p for p in pv.manifest_problems(manifest))
    entry["mapping_justification"] = "a reviewed, written reason"
    assert pv.manifest_problems(manifest) == []


def test_every_label_needs_an_explicit_target_and_a_reason_when_unmapped() -> None:
    manifest = copy.deepcopy(GOOD)
    del manifest["labels"]["classes"][0]["maps_to"]
    assert any("explicit maps_to" in p for p in pv.manifest_problems(manifest))
    manifest = copy.deepcopy(GOOD)
    del manifest["labels"]["classes"][-1]["reason"]
    assert any("no class and no recorded reason" in p for p in pv.manifest_problems(manifest))


def test_manifest_class_counts_add_up() -> None:
    counts = {e["name"]: e["count"] for e in GOOD["labels"]["classes"]}
    assert sum(counts.values()) == GOOD["images"]["total"] == 4752
    assert sum(e["count"] for e in GOOD["labels"]["classes"] if e["maps_to"]) == 3092


# -- leakage ---------------------------------------------------------------------------------------
def test_byte_identical_files_in_different_folds_are_detected_whatever_their_label() -> None:
    hashes = ["h1", "h2", "h1", "h3"]
    folds = np.array([0, 1, 2, 3])
    assert pv.straddling_duplicates(hashes, folds) == ["h1"]
    with pytest.raises(pv.ProvenanceError, match="straddle"):
        pv.require_no_leakage(hashes, folds)
    pv.require_no_leakage(hashes, np.array([2, 1, 2, 3]))  # copies inside one fold are fine


def test_exact_duplicates_are_counted() -> None:
    assert pv.exact_duplicate_count(["a", "b", "a", "a"]) == 2


# -- acceptance gate -------------------------------------------------------------------------------
def _test_block(macro_f1: float = 0.9, ece: float = 0.03, recall: float = 0.85) -> dict[str, Any]:
    return {
        "macro_f1": macro_f1,
        "ece": ece,
        "per_class": [{"recall": recall}, {"recall": 0.9}],
    }


def _acceptance(field: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    args: dict[str, Any] = {
        "test": _test_block(),
        "review": {"accepted_accuracy_ci_low": 0.95},
        "margin_over_handcrafted": 0.2,
        "out_of_scope_review_rate": 0.97,
        "criteria": CONFIG["acceptance"],
        "field_report": field,
    }
    args.update(overrides)
    result: dict[str, Any] = pl.evaluate_acceptance(**args)
    return result


def test_meeting_every_offline_criterion_is_not_approval_without_a_field_study() -> None:
    result = _acceptance()
    assert result["offline_passed"] is True
    assert result["field_evaluation"]["done"] is False
    assert result["approved_for_activation"] is False
    assert "no field evaluation" in result["decision"]


@pytest.mark.parametrize(
    ("override", "failing"),
    [
        ({"test": _test_block(macro_f1=0.5)}, "test_macro_f1"),
        ({"test": _test_block(ece=0.3)}, "ece"),
        ({"test": _test_block(recall=0.2)}, "min_class_recall"),
        ({"margin_over_handcrafted": 0.01}, "margin_over_handcrafted_macro_f1"),
        ({"review": {"accepted_accuracy_ci_low": 0.5}}, "auto_accepted_accuracy_ci_low"),
        ({"out_of_scope_review_rate": 0.4}, "out_of_scope_review_rate"),
    ],
)
def test_each_failed_offline_criterion_blocks_approval(
    override: dict[str, Any], failing: str
) -> None:
    field = {"n_images": 500, "macro_f1": 0.95, "accuracy_of_auto_accepted": 0.97}
    result = _acceptance(field=field, **override)
    assert result["offline"][failing]["passed"] is False
    assert result["offline_passed"] is False
    assert result["approved_for_activation"] is False  # a perfect field study cannot rescue it


def test_approval_needs_offline_and_a_large_enough_passing_field_study() -> None:
    good = {"n_images": 400, "macro_f1": 0.8, "accuracy_of_auto_accepted": 0.93}
    assert _acceptance(field=good)["approved_for_activation"] is True
    too_few = _acceptance(field={**good, "n_images": 50})
    assert too_few["approved_for_activation"] is False
    assert _acceptance(field={**good, "macro_f1": 0.4})["approved_for_activation"] is False
    unsafe = _acceptance(field={**good, "accuracy_of_auto_accepted": 0.5})
    assert unsafe["approved_for_activation"] is False


def test_the_criteria_are_fixed_in_the_config_not_in_code() -> None:
    offline = CONFIG["acceptance"]["offline"]
    assert offline["min_test_macro_f1"] > 0 and offline["max_ece"] > 0
    assert CONFIG["acceptance"]["field"]["required"] is True


# -- legacy research code and the withdrawn model --------------------------------------------------
@pytest.mark.parametrize(
    "module", ["cross_dataset", "multi_dataset_experiment", "trashbox_experiment"]
)
def test_withdrawn_research_modules_refuse_to_run(module: str) -> None:
    mod = importlib.import_module(f"ml.waste_classification.research.{module}")
    assert mod.WITHDRAWN is True
    with pytest.raises(SystemExit, match="withdrawn"):
        mod.main()


def test_the_trashnet_loader_no_longer_exists() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("ml.waste_classification.data.trashnet")


def test_the_withdrawn_registry_entry_is_marked_and_no_entry_is_active() -> None:
    registry = REPO / "ml" / "model_registry" / "waste_classification"
    old = yaml.safe_load((registry / "1.0.0.yaml").read_text())
    assert old["status"] == "withdrawn"
    assert "trashnet" in old["withdrawn"]["reason"].lower()
    for path in registry.glob("*.yaml"):
        assert yaml.safe_load(path.read_text())["status"] != "active"
