"""
Vera merchant engagement composer.

Contract:
    compose(category, merchant, trigger, customer=None) -> dict

Deterministic, stdlib-only, context-grounded. No invented merchant/customer facts.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
import re

ACTION_KINDS = {
    "perf_dip","perf_spike","milestone_reached","profile_incomplete",
    "festival_upcoming","weather_heatwave","local_news_event",
    "competitor_opened","category_trend_movement","renewal_due",
    "offer_opportunity","curious_ask_due","scheduled_recurring",
    "active_planning_intent","review_theme_emerged","winback_eligible",
    "gbp_unverified","category_seasonal","ipl_match_today","seasonal_perf_dip",
    "dormant_with_vera",
}
INFO_KINDS = {"research_digest","research_digest_release","regulation_change",
              "category_research_digest_release","cde_opportunity","supply_alert"}
CUSTOMER_KINDS = {
    "recall_due","customer_lapsed_soft","customer_lapsed_hard","appointment_tomorrow",
    "unplanned_slot_open","chronic_refill_due","trial_followup","wedding_package_followup",
}
CATEGORY_STYLE = {
    "dentists": "clinical-peer",
    "salons": "warm-practical",
    "restaurants": "operator-peer",
    "gyms": "coaching",
    "pharmacies": "trustworthy-precise",
}
AUTO_REPLY_PATTERNS = [
    r"thank you for contacting", r"thanks for contacting", r"your message has been received",
    r"we will get back", r"our team will", r"automated response", r"this is an automated",
    r"main aapki .* team tak", r"jaankari ke liye.*shukriya",
]

def _ident(obj): return (obj or {}).get("identity") or {}
def _name(merchant):
    return _ident(merchant).get("name") or merchant.get("name") or "there"
def _owner(merchant):
    return _ident(merchant).get("owner_first_name")
def _category(category, merchant):
    return (category or {}).get("slug") or merchant.get("category_slug") or "business"
def _payload(trigger): return (trigger or {}).get("payload") or {}
def _kind(trigger): return str((trigger or {}).get("kind") or "").lower()
def _first(d, *paths):
    for path in paths:
        x=d
        for k in path.split("."):
            if not isinstance(x,dict) or k not in x: x=None; break
            x=x[k]
        if x not in (None,"",[]): return x
    return None
def _pct(x):
    if isinstance(x,(int,float)):
        return f"{x*100:.0f}%" if abs(x)<=1 else f"{x:.0f}%"
    return str(x)
def _active_offer(merchant):
    for o in merchant.get("offers") or []:
        if str(o.get("status","")).lower()=="active":
            return o.get("title")
    return None
def _digest_item(category, item_id=None):
    items=(category or {}).get("digest") or []
    if item_id:
        for item in items:
            if item.get("id")==item_id: return item
    return items[0] if items else {}
def _language_hint(merchant, customer=None):
    ctx=customer or merchant
    ci=_ident(ctx)
    pref=ci.get("language_pref") or ci.get("language")
    langs=ci.get("languages") or []
    if isinstance(pref,str) and ("hi" in pref.lower() or "hindi" in pref.lower()): return "hi-en"
    if isinstance(pref,str) and ("te" in pref.lower() or "telugu" in pref.lower()): return "regional-en"
    if isinstance(langs,list) and "hi" in [str(x).lower() for x in langs]: return "hi-en"
    return "en"

def _hook(category, merchant, trigger):
    k=_kind(trigger); p=_payload(trigger); perf=merchant.get("performance") or {}
    if k in INFO_KINDS or "research" in k or "digest" in k:
        item=_digest_item(category, p.get("top_item_id") or p.get("digest_item_id") or p.get("alert_id"))
        title=item.get("title") or item.get("headline")
        source=item.get("source")
        if title:
            return title + (f" — {source}" if source else "")
        if p.get("molecule") and p.get("affected_batches"):
            return f"{p['molecule']} recall for batches {', '.join(p['affected_batches'])}"
    if k in {"perf_spike","perf_dip","seasonal_perf_dip"}:
        delta=p.get("delta_pct")
        metric=p.get("metric")
        if delta is None:
            d=perf.get("delta_7d") or {}
            metric=metric or (next(iter(d),None))
            delta=d.get(metric) if metric else None
        if metric and delta is not None:
            return f"{metric.replace('_',' ')} {_pct(delta)} vs baseline"
    if k=="milestone_reached":
        return str(p.get("milestone") or p.get("value") or "a new milestone")
    if k=="competitor_opened":
        n=p.get("competitor_name") or "a new competitor"
        dist=p.get("distance_km") or p.get("distance")
        return f"{n} opened {dist} km away" if dist else n
    if k=="category_trend_movement":
        q=p.get("query"); d=p.get("delta_yoy")
        return f'"{q}" searches are {_pct(d)} YoY' if q and d is not None else (f'"{q}" is moving' if q else None)
    if k in {"festival_upcoming","festival"}:
        return f"{p.get('festival') or p.get('name') or 'an upcoming local event'}"
    if k=="weather_heatwave":
        t=p.get("temperature_c") or p.get("temp_c")
        return f"{t}°C today" if t is not None else "today's heatwave"
    if k in {"local_news_event","ipl_match_today"}:
        if k=="ipl_match_today": return f"{p.get('match')} at {p.get('match_time_iso','').replace('T',' ')}"
        return str(p.get("headline") or p.get("title") or "a local event")
    if k=="regulation_change":
        deadline=p.get("deadline_iso")
        return str(p.get("title") or p.get("headline") or "a regulation update") + (f" — deadline {deadline}" if deadline else "")
    if k=="review_theme_emerged":
        return f"{p.get('theme','review theme').replace('_',' ')} ({p.get('occurrences_30d','?')} mentions; {p.get('trend','rising')})"
    if k=="winback_eligible":
        return f"{p.get('days_since_expiry','?')} days since expiry; {p.get('lapsed_customers_added_since_expiry','?')} lapsed customers added"
    if k=="gbp_unverified":
        return f"GBP is unverified; estimated uplift is {_pct(p.get('estimated_uplift_pct'))}"
    if k=="category_seasonal":
        trends=p.get("trends") or []
        return f"{p.get('season','seasonal demand')}: {', '.join(trends[:3])}"
    if k=="active_planning_intent":
        return str(p.get("intent_topic") or p.get("merchant_last_message") or "your new program")
    if k=="renewal_due":
        return f"Pro plan has {p.get('days_remaining')} days remaining"
    if k=="cde_opportunity":
        item=_digest_item(category,p.get("digest_item_id"))
        return f"{item.get('title','training opportunity')} ({p.get('credits','?')} credits; {p.get('fee','fee')})"
    if k in CUSTOMER_KINDS:
        if p.get("due_date"): return f"due {p['due_date']}"
        if p.get("appointment_time") or p.get("slot"): return f"appointment {p.get('appointment_time') or p.get('slot')}"
        if p.get("wedding_date"): return f"{p.get('days_to_wedding','?')} days to wedding"
    return str(merchant.get("signals",[None])[0]) if merchant.get("signals") else None

def _customer_message(category, merchant, trigger, customer):
    k=_kind(trigger); p=_payload(trigger); ci=_ident(customer)
    name=ci.get("name") or "there"; merchant_name=_name(merchant)
    offer=_active_offer(merchant); pref=_first(customer,"preferences.preferred_slots")
    lang=_language_hint(merchant,customer)
    if k=="appointment_tomorrow":
        slot=p.get("appointment_time") or p.get("slot")
        body=f"Hi {name}, {merchant_name} here — your appointment is tomorrow"
        if slot: body+=f" at {slot}"
        body+=". Reply YES to confirm, or STOP to opt out."
    elif k=="recall_due":
        slots=p.get("available_slots") or []
        slot_text=" / ".join(s.get("label","") for s in slots[:2] if s.get("label"))
        service=str(p.get("service_due","follow-up")).replace("_"," ")
        body=f"Hi {name}, {merchant_name} here — your {service} is due"
        if p.get("due_date"): body+=f" on {p['due_date']}"
        if slot_text: body+=f". We have {slot_text}"
        if offer: body+=f". Current option: {offer}"
        body+=". Reply YES and we’ll arrange it, or STOP to opt out."
    elif k=="wedding_package_followup":
        body=f"Hi {name}, {merchant_name} here — {p.get('days_to_wedding','')} days to your wedding"
        body+=f". Your next step window is {str(p.get('next_step_window_open','')).replace('_',' ')}"
        body+=". Reply YES if you want us to schedule it, or STOP to opt out."
    elif k=="chronic_refill_due":
        if _category(category,merchant)=="pharmacies":
            body=f"Hi {name}, {merchant_name} here — your repeat prescription refill window is due"
            if offer: body+=f". We can use {offer}"
            body+=". Reply YES to arrange the refill, or STOP to opt out."
        else:
            body=f"Hi {name}, {merchant_name} here — your follow-up window is due"
            if offer: body+=f". Current option: {offer}"
            body+=". Reply YES if you'd like us to arrange it, or STOP to opt out."
    else:
        state=k.replace("customer_","").replace("_"," ")
        body=f"Hi {name}, {merchant_name} here — a {state} follow-up is available"
        if offer: body+=f" ({offer})"
        if pref: body+=f". Your preferred timing is {pref}"
        body+=". Reply YES if you'd like us to arrange it, or STOP to opt out."
    if lang=="hi-en":
        body=body.replace("Reply YES to confirm, or STOP to opt out.","YES reply kijiye to confirm; STOP se opt out.")
        body=body.replace("Reply YES and we’ll arrange it, or STOP to opt out.","YES reply kijiye, hum arrange kar denge; STOP se opt out.")
        body=body.replace("Reply YES if you want us to schedule it, or STOP to opt out.","YES reply kijiye, hum schedule kar denge; STOP se opt out.")
        body=body.replace("Reply YES to arrange the refill, or STOP to opt out.","YES reply kijiye refill arrange karne ke liye; STOP se opt out.")
        body=body.replace("Reply YES if you'd like us to arrange it, or STOP to opt out.","YES reply kijiye agar arrange karna hai; STOP se opt out.")
    return body, "binary_yes_stop"

def _merchant_message(category, merchant, trigger):
    k=_kind(trigger); name=_name(merchant); cat=_category(category,merchant); p=_payload(trigger)
    hook=_hook(category,merchant,trigger); offer=_active_offer(merchant); lang=_language_hint(merchant)
    if k in INFO_KINDS or "research" in k or "digest" in k:
        body=f"{name}, one item from this week's {cat} update is worth a look: {hook or 'a new update'}."
        if merchant.get("signals"): body+=f" It lines up with your current signal: {merchant['signals'][0]}."
        body+=" Want me to pull the practical takeaway?"
    elif k=="perf_dip":
        body=f"{name}, your {p.get('metric','dashboard')} needs attention: {hook or 'it moved down'}."
        if offer: body+=f" You currently have {offer} active."
        body+=" Want me to show the lowest-effort fix first?"
    elif k=="perf_spike":
        body=f"{name}, positive movement: {hook or 'your numbers improved'}."
        body+=" Want the 2-minute breakdown of what likely drove it?"
    elif k=="active_planning_intent":
        topic=p.get("merchant_last_message") or hook or "the new program"
        body=f"{name}, I picked up your plan: “{topic}”"
        body+=" I can turn that into a concrete first draft now. Want me to draft it?"
    elif k=="review_theme_emerged":
        body=f"{name}, one review theme is moving: {hook}."
        body+=" Want me to turn that into a 3-step fix you can use this week?"
    elif k=="supply_alert":
        body=f"{name}, heads up: {hook}."
        body+=" Please check the affected stock/customer list before the next dispense. Want me to format the pull list?"
    elif k=="category_seasonal":
        body=f"{name}, seasonal demand has shifted: {hook}."
        body+=" Want me to turn that into one shelf/profile change using your existing catalog?"
    elif k=="gbp_unverified":
        body=f"{name}, your GBP is still unverified; the context estimates {_pct(p.get('estimated_uplift_pct'))} uplift."
        body+=" Want the shortest verification checklist?"
    elif k=="winback_eligible":
        body=f"{name}, there’s a concrete win-back window: {hook}."
        body+=" Want me to build a message around your current offer?"
    elif k=="renewal_due":
        body=f"{name}, your {p.get('plan','plan')} has {p.get('days_remaining','?')} days left."
        body+=" Want me to show the renewal step before it becomes urgent?"
    elif k=="cde_opportunity":
        body=f"{name}, this is relevant to your practice: {hook}."
        body+=" Want me to pull the registration details?"
    elif k=="competitor_opened":
        body=f"{name}, local competition changed: {hook}."
        body+=" Want me to show the first profile/offers change I'd make?"
    elif k in {"festival_upcoming","ipl_match_today","weather_heatwave","local_news_event"}:
        body=f"{name}, there’s a timely {cat} angle: {hook or 'an upcoming event'}."
        if offer: body+=f" You already have {offer}; I can build the message around it."
        else: body+=" Want me to draft a service-led message from your existing catalog?"
    elif k=="curious_ask_due":
        body=f"{name}, quick question for {cat}"
        if offer: body+=f": is {offer} still your priority this week?"
        else: body+=": what are customers asking for most this week?"
        body+=" I’ll turn the answer into one usable post/reply."
    elif k in {"seasonal_perf_dip","dormant_with_vera"}:
        body=f"{name}, a quieter period is showing up: {hook or 'activity has softened'}."
        body+=" Want one low-effort action rather than a broad campaign?"
    else:
        body=f"{name}, quick check on {cat}: {hook or 'there is a new action worth considering'}."
        body+=" Want me to draft the next step?"
    if lang=="hi-en":
        replacements = {
            "Want me to pull the practical takeaway?": "Practical takeaway nikaal du?",
            "Want me to show the lowest-effort fix first?": "Pehle lowest-effort fix dikhaun?",
            "Want the 2-minute breakdown of what likely drove it?": "2-minute breakdown bheju?",
            "Want me to turn that into a 3-step fix you can use this week?": "Isko 3-step fix mein turn kar du?",
            "Want me to format the pull list?": "Pull list format kar du?",
            "Want me to turn that into one shelf/profile change using your existing catalog?": "Existing catalog se ek shelf/profile change draft kar du?",
            "Want me to show the renewal step before it becomes urgent?": "Urgent hone se pehle renewal step dikhaun?",
            "Want me to pull the registration details?": "Registration details nikaal du?",
            "Want me to show the first profile/offers change I'd make?": "Pehla profile/offers change dikhaun?",
            "Want me to draft a service-led message from your existing catalog?": "Existing catalog se service-led message draft kar du?",
            "Want me to build a message around your current offer?": "Current offer ke around message bana du?",
            "Want one low-effort action rather than a broad campaign?": "Broad campaign ke bajay ek low-effort action try karein?",
        }
        for a,b in replacements.items(): body=body.replace(a,b)
    return body, "open_ended"

def compose(category: dict, merchant: dict, trigger: dict, customer: Optional[dict]=None) -> dict:
    k=_kind(trigger)
    customer_scope=(trigger or {}).get("scope")=="customer" or customer is not None or k in CUSTOMER_KINDS
    if customer_scope and customer:
        body,cta=_customer_message(category,merchant,trigger,customer); send_as="merchant_on_behalf"
    else:
        body,cta=_merchant_message(category,merchant,trigger); send_as="vera"
        if k in ACTION_KINDS and k != "curious_ask_due":
            cta="binary_yes_stop"
            body += " Reply YES if you want me to do it, or STOP to opt out."
    suppression=(trigger or {}).get("suppression_key") or (trigger or {}).get("id") or f"{k}:{merchant.get('merchant_id','unknown')}"
    rationale=f"Trigger={k or 'unspecified'}; grounded in supplied category/merchant"
    if customer_scope: rationale+=" + customer context; consent-aware binary CTA"
    else: rationale+=f"; {CATEGORY_STYLE.get(_category(category,merchant),'peer-practical')} voice; single ask"
    return {"body":body,"cta":cta,"send_as":send_as,"suppression_key":suppression,"rationale":rationale}

def is_auto_reply(message: str, prior_messages: Optional[List[str]]=None) -> bool:
    m=(message or "").strip().lower()
    if not m: return True
    if any(re.search(p,m) for p in AUTO_REPLY_PATTERNS): return True
    if prior_messages:
        norm=lambda s: re.sub(r"\s+"," ",s.lower()).strip()
        return sum(norm(x)==norm(message) for x in prior_messages)>=2
    return False

def detect_intent(message: str) -> str:
    m=(message or "").lower()
    if re.search(r"\b(stop|unsubscribe|not interested|no thanks|don't|dont)\b",m): return "stop"
    if re.search(r"\b(join|sign me up|register|go ahead|let'?s do it|yes|proceed|start)\b",m): return "action"
    if "update my google" in m or "update profile" in m: return "profile_update"
    if "price" in m or "cost" in m: return "pricing"
    return "question"

def compose_template(category: dict, trigger: dict, merchant: dict, customer: Optional[dict]=None) -> dict:
    """First-touch wrapper for the WhatsApp 24h template constraint."""
    out=compose(category,merchant,trigger,customer)
    return {**out, "template_name":"vera_engagement_v1",
            "template_params":[_name(merchant), out["body"][:180]]}
