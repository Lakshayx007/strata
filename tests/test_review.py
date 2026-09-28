import pandas as pd

from analysis.labeling import review


def _labels(rows):
    cols = ["doc_id", "draft_label", "draft_from", "draft_to", "draft_direction", "draft_evidence",
            "my_label", "my_from", "my_to", "my_direction", "notes"]
    return pd.DataFrame(rows, columns=cols)


def test_code_map_reads_merge_and_rename_only():
    tax = pd.DataFrame({"code": ["cost", "skills_team", "ecosystem_fit"],
                        "my_decision": ["keep", "merge-into", "rename"],
                        "my_new_name": [None, "operational_simplicity", "ecosystem"]})
    assert review.code_map(tax) == {"skills_team": "operational_simplicity", "ecosystem_fit": "ecosystem"}


def test_blank_reviewer_cell_keeps_draft_and_merge_is_not_a_disagreement():
    sheet = _labels([
        [1, "skills_team", "aws", "snowflake", "leave", "e1", None, None, None, None, None],
        [2, "none", "none", "none", "none", "e2", "cost", None, None, "adopt", float("nan")],
        [3, "cost", "aws", "snowflake", "leave", "e3", "operational_simplicity", None, None, None, "note"],
    ])
    final = review.final_labels(sheet, {"skills_team": "operational_simplicity"})
    assert list(final.taxonomy_code) == ["operational_simplicity", "cost", "operational_simplicity"]
    assert list(final.draft_taxonomy_code) == ["operational_simplicity", "none", "cost"]
    assert final.direction.tolist() == ["leave", "adopt", "leave"]
    a = review.agreement(final)
    assert a["all rows"]["taxonomy_code"]["agree"] == 1
    assert a["draft = none"]["taxonomy_code"]["n"] == 1
    assert pd.isna(a["draft = none"]["taxonomy_code"]["kappa"])  # one rater used a single value


def test_render_says_model_vs_model():
    sheet = _labels([[1, "cost", "aws", "snowflake", "leave", "e", None, None, None, None, None],
                     [2, "none", "none", "none", "none", "e", None, None, None, None, None]])
    text = review.render("seed_v1", "claude_review", review.agreement(review.final_labels(sheet, {})))
    assert "model-vs-model" in text and "human" not in text
