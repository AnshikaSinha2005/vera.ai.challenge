import json, subprocess, sys, time, urllib.request
from bot import compose, is_auto_reply, detect_intent

def test_compose():
    c={"slug":"dentists","digest":[{"title":"3-mo fluoride recall cuts caries 38% better than 6-mo","source":"JIDA Oct 2026, p.14"}]}
    m={"merchant_id":"m1","category_slug":"dentists","identity":{"name":"Dr. Meera's Dental Clinic","languages":["en","hi"]},
       "performance":{"views":2410,"ctr":0.021,"delta_7d":{"views_pct":0.18}},
       "offers":[{"title":"Dental Cleaning @ ₹299","status":"active"}],
       "signals":["stale_posts:22d"]}
    t={"id":"t1","kind":"research_digest","scope":"merchant","suppression_key":"r:1","payload":{}}
    o=compose(c,m,t,None)
    assert o["send_as"]=="vera" and "38%" in o["body"] and "JIDA" in o["body"]

def test_customer():
    c={"slug":"dentists"}
    m={"merchant_id":"m1","category_slug":"dentists","identity":{"name":"Dr. Meera's Dental Clinic"},"offers":[{"title":"Dental Cleaning @ ₹299","status":"active"}]}
    cust={"customer_id":"c1","identity":{"name":"Priya","language_pref":"hi-en mix"},"relationship":{"last_visit":"2026-05-12"},"preferences":{"preferred_slots":"weekday evening"}}
    t={"kind":"recall_due","scope":"customer","payload":{"due_date":"2026-11-12"},"suppression_key":"recall:c1"}
    o=compose(c,m,t,cust)
    assert o["send_as"]=="merchant_on_behalf" and "Priya" in o["body"] and "₹299" in o["body"]

def test_routing():
    assert is_auto_reply("Thank you for contacting us. We will get back to you.")
    assert detect_intent("yes, I want to join")=="action"
    assert detect_intent("not interested")=="stop"

if __name__=="__main__":
    test_compose(); test_customer(); test_routing(); print("smoke tests: PASS")
