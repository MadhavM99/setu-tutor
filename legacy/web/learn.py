"""Learn and teach Raju (paper §5): learn -> practise -> check -> fix Raju's planted mistake -> explain why -> review.
The page draws whatever question is open in the learner's saved record (tutor.screen), so a refresh or a
server restart continues exactly where the learner was."""
import html
import streamlit as st
from setu.checker import NO_ERROR
from setu.contracts import LEVEL_NAMES
from setu.web import (tutor, learner, style, card, card_for, feedback, raju_bubble, aids, didi, didi_bubble,
                      learned_so_far, path_bar, sentence_card, scene_box, prepare_in_background)

style()
t, lid = tutor(), learner()
ss = st.session_state


def go_next() -> None:
    r = t.next(lid)
    ss["done"] = r["message"] if r["kind"] == "done" else None
    if r["kind"] == "lesson":
        ss[f"cards-{r['unit']}"] = 0


def submit(text: str) -> None:
    text = (text or "").strip()
    if not text:
        return
    before = t.store.load(lid).pending or {}
    res = t.answer(lid, text)
    teacher = didi()
    if teacher is not None and before.get("kind") == "drill" and res.get("verdict") == "wrong" and res.get("next"):
        item = t.items[res["next"]["item"]][1]                  # Didi's hint for the letter just missed
        seen, ids = learned_so_far(t, lid)
        hint, src, _ = teacher.hint(t.by_id[before["unit"]], item, seen, ids)
        if hint:
            res["didi"] = hint
    if res.get("verdict") == "correct" and before.get("unit"):
        # which letter was just answered right -> show its picture with the answer
        unit = t.by_id[before["unit"]]
        item = None
        if before["kind"] == "drill":
            item = t.items[before["queue"][0]][1]
        elif before["kind"] == "check":
            item = unit.check
        elif before["kind"] == "raju":
            item = t.items[before["item"]][1]
        elif before["kind"] == "followup":
            fu = t._fus(t.store.load(lid), unit)
            item = fu[before["idx"]].item if before["idx"] < len(fu) else None
        if item is not None and item.kind == "letter" and unit.level == 0:
            res["reveal"] = {"unit": unit.unit_id, "telugu": item.prompt}
    still = t.store.load(lid).pending
    if teacher is not None and before.get("kind") in ("raju", "followup") and res.get("verdict") == "wrong" and still:
        # the coach (paper §5): on a wrong fix, a hint in Hindi that is checked to contain no answer
        unit = t.by_id[before["unit"]]
        if before["kind"] == "raju":
            item = t.items[before["item"]][1]
        else:
            fu = t._fus(t.store.load(lid), unit)[before["idx"]]
            item = fu.item
        if item is not None:
            seen, ids = learned_so_far(t, lid)
            hint, src, _ = teacher.hint(unit, item, seen, ids)
            if hint:
                res["didi"] = hint
    ss["fb"] = res
    if "error" not in res and t.store.load(lid).pending is None:   # this question is finished: bring the next one
        go_next()
    st.rerun()


def answer_form(key: str, label: str, allow_ok: bool = False) -> None:
    with st.form(key, clear_on_submit=True, border=False):
        text = st.text_input(label, key=f"{key}-text", placeholder="यहाँ लिखो और Enter दबाओ")
        cols = st.columns([1, 1, 2]) if allow_ok else st.columns([1, 3])
        sent = cols[0].form_submit_button("जवाब दो", type="primary", width="stretch")
        ok = cols[1].form_submit_button("✓ कोई गलती नहीं", width="stretch") if allow_ok else False
    if ok:
        submit(NO_ERROR)
    elif sent:
        submit(text)


def ai_card(unit, i: int) -> None:
    """A lesson card with its AI teaching aids. They are made the first time anyone sees this card (a few
    seconds), then kept for everyone. Buttons ask for another trick / picture, or like the trick."""
    a, line = aids(), unit.lesson[i]
    if unit.level == 3:                                   # a rule: the sentence pair with a reading aid
        sentence_card(line.model_dump())
        return
    k = a.key(unit, line)
    tried = ss.setdefault("aid_tried", set())
    have = a.get(unit, line)
    want_trick = a.llm is not None and "trick" not in have
    want_pic = a.images is not None and "picture" not in have and line.example
    problems = []
    if (want_trick or want_pic) and k not in tried:
        tried.add(k)
        with st.spinner("✨ AI इस अक्षर के लिए तरकीब और चित्र बना रहा है… (पहली बार 10–30 सेकंड, फिर हमेशा तुरंत)"):
            if want_trick:
                r = a.trick(unit, line)
                if r and r.get("status") == "failed":
                    problems.append("तरकीब: " + "; ".join(", ".join(x["reasons"]) for x in r["rejected"])[:160])
            if want_pic:
                r = a.picture(unit, line)
                if r and r.get("status") == "failed":
                    problems.append("चित्र: " + " / ".join(r.get("tries", []) + [f"{m} → {res}" for m, _, res in r.get("attempts", [])][-3:])[:300])
        ss[f"aid-problems-{k}"] = problems
        have = a.get(unit, line)
    card(line.model_dump(), aid=have)
    for msg in ss.get(f"aid-problems-{k}", []):
        st.caption("⚠️ " + msg)
    if a.llm is None and a.images is None:
        return
    b1, b2, b3 = st.columns(3)
    if a.llm is not None and b1.button("🔄 दूसरी तरकीब", key=f"tr-{k}", width="stretch"):
        with st.spinner("नई तरकीब…"):
            a.trick(unit, line, fresh=True)
        st.rerun()
    if "trick" in have and b2.button("👍 ये याद रह गई", key=f"like-{k}", width="stretch"):
        a.mark(k, "trick", "liked"); st.toast("शुक्रिया! Teacher इसे देखेंगे।"); st.rerun()
    if a.images is not None and line.example and b3.button("🖼️ दूसरा चित्र", key=f"pic-{k}", width="stretch"):
        with st.spinner("नया चित्र… (10–20 सेकंड)"):
            r = a.picture(unit, line, fresh=True)
        if r and r.get("status") == "failed":
            ss[f"aid-problems-{k}"] = ["चित्र: " + " / ".join(r.get("tries", []))[:300]]
        st.rerun()


def ask_didi(unit_id: str) -> None:
    """Ask the AI teacher a doubt about this lesson. Only on cards and in the drill (never during the scored
    check or while teaching Raju)."""
    teacher = didi()
    if teacher is None:
        return
    key = f"didi-{unit_id}"
    talk = ss.setdefault(key, [])
    with st.expander("🙋 दीदी से पूछो" + (f" ({len(talk)})" if talk else ""), expanded=bool(talk)):
        for q, a in talk[-4:]:
            with st.chat_message("आप", avatar="🙂"):
                st.write(q)
            didi_bubble(a)
        with st.form(f"askf-{unit_id}", clear_on_submit=True, border=False):
            q = st.text_input("सवाल", placeholder="जैसे: ఖ और క में फ़र्क कैसे याद रखूँ?", label_visibility="collapsed")
            sent = st.form_submit_button("पूछो")
        if sent and q.strip():
            seen, ids = learned_so_far(t, lid)
            with st.spinner("दीदी सोच रही हैं…"):
                ans, src, rej = teacher.ask(t.by_id[unit_id], q, seen, ids)
            if src != "model":
                t.store.queue_for_teacher({"learner": lid, "kind": "didi", "unit": unit_id, "question": q,
                                           "rejected": [r["reasons"] for r in rej]})
            talk.append((q.strip(), ans))
            st.rerun()


def ask_line(prompt: str, kind: str, how: str, check: bool = False) -> None:
    if kind == "sentence":
        st.markdown(f'<div class="setu-sub">Telugu में लिखो:</div><div class="setu-ask-s">“{html.escape(prompt)}”</div>'
                    f'<div class="setu-sub">{html.escape(how)}</div>', unsafe_allow_html=True)
    else:
        q = prompt if check else f"{prompt} = ?"
        st.markdown(f'<div class="setu-ask">{html.escape(q)}</div><div class="setu-sub">{html.escape(how)}</div>',
                    unsafe_allow_html=True)


def header(s: dict, what: str) -> None:
    step = s.get("step") or {}
    if step:
        st.caption(f"{step['chapter']} · {step['module']}")
        if s["kind"] in ("raju", "followup"):
            st.markdown(f"### `{step['no']}` {step['title']}")
        else:
            st.markdown(f"### `{step['no']}` {html.escape(s['title'])}")
        st.caption(what)
    else:
        st.caption(f"Level {s['level']} · {LEVEL_NAMES[s['level']]} · {s['unit']} · {s['title']} · **{what}**")


def celebrate(res: dict) -> None:
    md = (res or {}).get("module_done")
    if md and not ss.get(f"cheered-{md['module']}"):
        ss[f"cheered-{md['module']}"] = True
        st.balloons()
    if md:
        st.success(f"🎉 **{md['module']} पूरा!** Raju ने सब सीख लिया।" + (f" अब: **{md['next']}**" if md.get("next") else ""))


s = t.screen(lid)

# ---------- nothing open: start, or "done for today" ----------
if s["kind"] == "idle":
    celebrate(ss.get("fb"))
    feedback(ss.get("fb"))
    if ss.get("done"):
        st.info(ss["done"])
        st.caption("Demo: sidebar → Demo controls → ⏩ समय आगे करो, और देखो Raju क्या भूलता है।")
        if st.button("फिर देखो", type="primary"):
            go_next(); st.rerun()
    else:
        st.title("🌉 Setu")
        st.write("Hindi से Telugu। आप **सीखते** हो, फिर अपने AI सहपाठी **Raju को सिखाते** हो। "
                 "Raju वही गलतियाँ करता है जो Hindi बोलने वाले करते हैं — आप ठीक करोगे और समझाओगे क्यों।")
        st.markdown("**हर module का रास्ता**")
        path_bar("", True)
        st.markdown("1. **📖 सीखो** — नया अक्षर या नियम, Hindi में समझाया हुआ (वाक्य वाले chapter में एक दृश्य के साथ)  \n"
                    "2. **⚡ अभ्यास** — खुद लिखो; गलती हुई तो वही फिर, दीदी hint देंगी  \n"
                    "3. **✅ जाँच** — एक नया सवाल, बिना hint  \n"
                    "4. **🧒 Raju की गलती ठीक करो** — module के आख़िर में; सही वाक्य खुद लिखो  \n"
                    "5. **❓ क्यों? समझाओ** — अपने शब्दों में; नियम की मुख्य बात होनी चाहिए  \n"
                    "6. **🔁 दोहराओ** — जब आप भूलने लगोगे, Raju भी भूल जाएगा और फिर पूछेगा")
        st.caption("अध्याय 1 अक्षर → अध्याय 2 शब्द → अध्याय 3 वाक्य (ऑटो स्टैंड, मेस, मकान-मालिक…)। "
                   "अक्षर आते हैं? Settings → 'सीधे यहाँ से शुरू करो'।")
        if st.button("शुरू करो ▶", type="primary"):
            ss["fb"] = None
            go_next(); st.rerun()

# ---------- lesson cards, then the drill ----------
elif s["kind"] == "drill":
    key = f"cards-{s['unit']}"
    i, n = ss.get(key, len(s["lesson"])), len(s["lesson"])   # after a refresh, go straight to the drill
    rules = s["level"] == 3
    if i < n:
        header(s, f"नया · {'वाक्य' if rules else 'कार्ड'} {i + 1}/{n}")
        path_bar("learn", rules)
        if i == 0:
            prepare_in_background(t.by_id[s["unit"]])     # the other cards' pictures are made meanwhile
            celebrate(ss.get("fb"))
            feedback(ss.get("fb"))
            if rules:
                scene_box(t, lid, t.by_id[s["unit"]])
            if s.get("tip"):
                st.info(f"💡 {s['tip']}")
        st.progress((i + 1) / n)
        ai_card(t.by_id[s["unit"]], i)
        c1, c2 = st.columns(2)
        ask_didi(s["unit"])
        if i > 0 and c1.button("← पिछला", width="stretch"):
            ss[key] = i - 1; ss["fb"] = None; st.rerun()
        if c2.button("आगे →" if i < n - 1 else "अभ्यास शुरू करो ⚡", type="primary", width="stretch"):
            ss[key] = i + 1; ss["fb"] = None; st.rerun()
    else:
        header(s, "अभ्यास (गिनती नहीं होगी)")
        path_bar("drill", rules)
        feedback(ss.get("fb"), s["unit"])
        ask_line(s["prompt"], s.get("item_kind"),
                 f'{s["how"]} · बाकी {s["left"]} · गलत हुआ तो {"वाक्य" if rules else "कार्ड"} फिर दिखेगा')
        answer_form(f"drill-{s['unit']}", "जवाब")
        ask_didi(s["unit"])
        with st.expander("कार्ड फिर से देखो"):
            for c in s["lesson"]:
                card_for(s["unit"], c, small=True)

# ---------- the scored check ----------
elif s["kind"] == "check":
    header(s, "CHECK · गिनती होगी · यहाँ कोई hint नहीं")
    path_bar("check", s["level"] == 3)
    feedback(ss.get("fb"))
    ask_line(s["question"].replace("Telugu में लिखो: ", "").strip("“”'").replace("' = ?", "") if s.get("item_kind") == "sentence"
             else s["question"], s.get("item_kind"), s["how"], check=True)
    answer_form(f"check-{s['unit']}", "जवाब")

# ---------- Raju: a mistake to fix, a line to judge, or a follow-up ----------
else:
    what = f"Raju का सवाल {s['number']}/{s['of']}" if s["kind"] == "followup" else "Raju को सिखाओ"
    header(s, what)
    step = s.get("step") or {}
    stage = "review" if step.get("no") == "🔁" else "why" if s.get("fu_kind") == "why" else "raju"
    path_bar(stage, s["level"] == 3)
    if step.get("no") not in (None, "🔁", "⭐") and s["kind"] == "raju" and not ss.get("fb"):
        st.info("🧒 Raju ने भी यही lessons पढ़े, पर वो गलतियाँ करता है। आपने जो सीखा, उससे उसकी गलती ठीक करो।")
    celebrate(ss.get("fb"))
    feedback(ss.get("fb"))
    raju_bubble(s["raju"], s.get("source", ""))
    st.caption(s["how"].replace("/ok", "‘✓ कोई गलती नहीं’ दबाओ"))
    answer_form(f"raju-{s['unit']}", "आपका जवाब", allow_ok=True)
