import re
from app.integrations.llm.schemas import ModerationDecision

def quick_rule(text: str) -> ModerationDecision | None:
    lower = text.lower()
    links = re.findall(r"https?://\S+", lower)
    # Narrow rule: repeated ad link flood. A lone URL or disagreement isn't spam.
    if len(links) >= 5 and len(set(links)) == 1:
        return ModerationDecision(action="delete", reason_code="spam", confidence=1)
    if not text.strip():
        return ModerationDecision(action="allow", reason_code="clean", confidence=1)
    return None
