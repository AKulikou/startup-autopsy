"""Lens knowledge packs: valid Agent Skills that reach the lens prompt."""

import pytest

from config import DOMAIN_LENSES, ENABLED_LENSES
from evaluators.evaluator import Evaluator
from evaluators.knowledge import KNOWLEDGE_DIR, load_knowledge, strip_frontmatter
from evaluators.lenses import LENSES, select_lenses

KNOWLEDGE_LENSES = [lens for lens in LENSES if lens.knowledge]


def test_frontmatter_is_stripped():
    assert strip_frontmatter("---\nname: x\ndescription: y\n---\n\n# Body\n") == "# Body"
    with pytest.raises(ValueError):
        strip_frontmatter("---\nname: x\n# never closed")


@pytest.mark.parametrize("lens", KNOWLEDGE_LENSES, ids=lambda lens: lens.key)
def test_knowledge_pack_is_a_skill_and_reaches_the_prompt(lens, fake_claude):
    skill = (KNOWLEDGE_DIR / lens.knowledge / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: ") and "\ndescription: " in skill.split("\n---", 1)[0]
    knowledge = load_knowledge(lens.knowledge)
    assert "name:" not in knowledge.splitlines()[0]
    prompt = Evaluator(lens, "An idea.").get_system_prompt()
    assert f"<domain_knowledge>\n{knowledge}\n</domain_knowledge>" in prompt


def test_references_are_included():
    assert "## Reference: red_flag_patterns.md" in load_knowledge("legal-counsel")


def test_domain_lenses_are_conditional_and_not_enabled_by_default():
    for lens in select_lenses(DOMAIN_LENSES):
        assert lens.applies_to, f"{lens.key} runs only where it fits, so it needs applies_to"
        assert lens.key not in ENABLED_LENSES


@pytest.mark.parametrize("lens", KNOWLEDGE_LENSES, ids=lambda lens: lens.key)
def test_skill_name_matches_its_folder(lens):
    # Agent Skills require the name to equal the folder name: lowercase letters, digits, hyphens.
    skill = (KNOWLEDGE_DIR / lens.knowledge / "SKILL.md").read_text(encoding="utf-8")
    assert skill.splitlines()[1] == f"name: {lens.knowledge}"
    assert all(c.islower() or c.isdigit() or c == "-" for c in lens.knowledge)
