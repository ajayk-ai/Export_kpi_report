"""Generate a short natural-language summary of the KPIs using Google Gemini."""
from google import genai

from .config import settings


def _build_prompt(kpis: list[dict], breakup: list[dict] | None = None) -> str:
    rows = "\n".join(
        f"- {k['month']}: opening={k['opening_order']}, new={k['new_order']}, "
        f"total={k['total_order']}, despatched={k['dispatched']}, balance={k['balance']}"
        for k in kpis
    )
    overdue = ""
    if breakup:
        top = "\n".join(
            f"- {b['country']}: overdue={b['over_due_breakup']}, "
            f"days_delay={b['days_delay']}"
            for b in breakup[:3]
            if b["over_due_breakup"] > 0
        )
        if top:
            overdue = f"\n\nTop overdue countries:\n{top}"
    return (
        "You are a supply chain analyst. Based on the monthly order KPIs below, "
        "write a concise executive summary as 3-5 short bullet points, each starting "
        "with '- '. Cover trends in new orders and despatch, the order balance "
        "direction, and the most overdue countries as a risk. After the bullets, add "
        "one final line starting exactly with 'Key Takeaway: ' giving the single most "
        "important conclusion. Keep each point to one line. No markdown headers, no "
        "bold, no numbering.\n\n"
        f"{rows}{overdue}"
    )


def generate_summary(kpis: list[dict], breakup: list[dict] | None = None) -> str:
    """Return an AI summary, or an empty string if unavailable.

    The summary is optional: if no API key is set, or the Gemini call fails
    (e.g. no network / blocked endpoint), we skip it rather than fail the whole
    report.
    """
    if not settings.gemini_api_key:
        return ""
    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=_build_prompt(kpis, breakup),
        )
        return (response.text or "").strip()
    except Exception as exc:  # noqa: BLE001 - optional feature, degrade gracefully
        print(f"[warn] Skipping AI summary — Gemini call failed: {exc}")
        return ""
