"""The user skill's frontmatter must load, or Claude sees a skill without a description."""

import pytest

from eval.trigger.run_trigger import DEFAULT_SKILL, check_frontmatter


def test_the_shipped_skill_frontmatter_loads():
    assert "business" in check_frontmatter(DEFAULT_SKILL)


def test_an_unquoted_colon_in_the_description_is_caught(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\nname: startup-autopsy\ndescription: Evaluate ideas. Not for: plain maths.\n---\n\nBody\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="mapping values"):
        check_frontmatter(skill)


def test_a_description_over_the_limit_is_caught(tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(f"---\nname: startup-autopsy\ndescription: {'x' * 1025}\n---\n", encoding="utf-8")
    with pytest.raises(ValueError, match="limit 1024"):
        check_frontmatter(skill)
