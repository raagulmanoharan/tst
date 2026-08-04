"""Walk-in briefs.

Walking into a commercial premises is the lowest-risk channel available — no
Indian regulation restricts it, unlike cold calls (TRAI), SMS (DLT) and
WhatsApp (Meta policy) — and practitioners report far better conversion from it
than from any remote channel.

This produces a one-screen brief to glance at before going in, not a script to
recite. Same voice rules as email: one person, one specific observation.
"""

from __future__ import annotations

from ..config import Operator
from ..discover.places import EphemeralPlace
from ..store.models import Lead, OutreachRecord
from .email import pick_headline_defect


def draft_walkin(
    lead: Lead,
    place: EphemeralPlace | None,
    operator: Operator,
) -> OutreachRecord | None:
    """Compose a walk-in brief. Returns None when there is no defect to lead with."""
    defect = pick_headline_defect(lead, place)
    if defect is None:
        return None

    business = (place.display_name if place else None) or "this business"
    address = (place.formatted_address if place else None) or "address: look up live before going"

    out_of_range = ""
    if lead.city.lower() != operator.city.lower():
        out_of_range = (
            f"\n! This lead is in {lead.city}, not {operator.city}. "
            f"Only worth a walk-in if you're already travelling there.\n"
        )

    body = f"""WALK-IN BRIEF — {business}
{address}
{out_of_range}
WHAT I FOUND
  {defect.observation.capitalize()}.
  Why it matters: {defect.consequence}.

OPENING LINE (say it, then stop talking)
  "Hi — I'm {operator.name}, I build websites for a few businesses around here.
   I was looking you up online and noticed {defect.observation}. Thought you'd
   want to know."

THEN
  - Show them on your phone. Don't describe it, let them see it.
  - Ask one question: "Is that something you've been meaning to sort out?"
  - If yes: offer to mock up what you'd change, free, and come back with it.
  - If no: leave it. Thank them, leave a card, go. Do not push.

WHAT TO BRING
  - Your phone, with their site already open to the problem
  - A card with {operator.site} on it

WHAT NOT TO DO
  - Don't quote a price standing at the counter
  - Don't pitch a package or list services
  - Don't ask for the owner if they're not there — get a name and come back
  - Don't leave a printed proposal; nobody reads them

IF THEY'RE INTERESTED
  Get an email address, not a phone number. Cold-calling them afterwards is a
  TRAI problem; replying to an email they gave you is not. Once they contact
  you first, phone and WhatsApp are both fine.
"""

    return OutreachRecord(channel="walkin", subject=f"Walk-in: {business}", body=body)
