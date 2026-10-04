"""Stateful multi-turn behavior for Vera judge replay."""
from dataclasses import dataclass, field
from typing import List, Dict
from bot import is_auto_reply, detect_intent

@dataclass
class ConversationState:
    conversation_id: str
    merchant_id: str
    customer_id: str|None = None
    turns: List[Dict] = field(default_factory=list)
    sent_bodies: List[str] = field(default_factory=list)
    auto_reply_count: int = 0
    unanswered_nudges: int = 0
    intent: str = "unknown"

def respond(state: ConversationState, merchant_message: str) -> dict:
    msg=(merchant_message or "").strip()
    state.turns.append({"from":"merchant","body":msg})
    if is_auto_reply(msg, state.sent_bodies):
        state.auto_reply_count += 1
        if state.auto_reply_count >= 2:
            return {"action":"end","rationale":"Detected repeated canned/automated responses; stopping instead of burning turns."}
        body="Samajh gayi. Team tak pahunchane se pehle, kya aap khud exact detail dekhna chahenge? Reply YES if useful."
        state.sent_bodies.append(body)
        return {"action":"send","body":body,"cta":"open_ended","rationale":"One retry after likely auto-reply, then stop if repeated."}
    intent=detect_intent(msg); state.intent=intent
    if intent=="stop":
        return {"action":"end","rationale":"Merchant explicitly declined; graceful exit."}
    if intent=="action":
        body="Done — aapne action ke liye green signal de diya. Main next step par move kar rahi hoon; agar koi required detail missing hai to sirf wohi poochungi."
        state.sent_bodies.append(body)
        return {"action":"send","body":body,"cta":"open_ended","rationale":"Explicit intent transition detected; do not re-qualify."}
    if intent=="profile_update":
        body="Sure — profile update mode mein move karte hain. Main pehle missing fields identify karungi, phir jo details available hain unke basis par next step bataungi."
        state.sent_bodies.append(body)
        return {"action":"send","body":body,"cta":"open_ended","rationale":"Recognized direct profile-update intent and moved to action."}
    if intent=="pricing":
        body="Bilkul. Main sirf wahi pricing share karungi jo current merchant context mein available hai. Aap jis service/offer ka naam bhej dein, main usi par focus karungi."
        state.sent_bodies.append(body)
        return {"action":"send","body":body,"cta":"open_ended","rationale":"Answers pricing intent without inventing a price."}
    if state.unanswered_nudges >= 2:
        return {"action":"end","rationale":"Conversation has reached the stop threshold."}
    body="Got it. Main isi point par focus karungi. Aap chahte hain main next step draft karun?"
    state.sent_bodies.append(body)
    return {"action":"send","body":body,"cta":"open_ended","rationale":"Keeps the thread focused with one clear next step."}
