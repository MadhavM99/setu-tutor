/* SETU voice: listen and say-it buttons. Progressive enhancement only: every page works without this file, and the
   buttons stay hidden unless the browser can do the job. Nothing here grades anything; only the checker grades.

   Listen:  <button class="speak" data-say="తెలుగు" data-audio="/static/audio/x.mp3" hidden>
            Plays the recorded file when data-audio is set and loads; otherwise the browser's own voice (te-IN).
   Say it:  <button class="say-it" data-expect="తెలుగు" data-heard="..." data-close="..." data-again="..." hidden>
            Listens once, shows what the browser heard and whether it is close. A practice mirror, not a mark.
   All wording comes from the Hindi catalog through data-* attributes; this file holds no words of its own. */
(function () {
  "use strict";
  var synth = window.speechSynthesis || null;
  var Rec = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var slow = false;
  try { slow = window.localStorage.getItem("setu.slow") === "1"; } catch (e) { /* storage may be blocked */ }

  function teluguVoice() {
    if (!synth) return null;
    var voices = synth.getVoices() || [];
    for (var i = 0; i < voices.length; i++) { if (/^te(-|_|$)/i.test(voices[i].lang)) return voices[i]; }
    return null;
  }

  function say(button) {
    var file = button.getAttribute("data-audio");
    var finish = function () { button.classList.remove("is-playing"); };
    button.classList.add("is-playing");
    if (file) {
      var audio = new Audio(file);
      audio.playbackRate = slow ? 0.7 : 1;
      audio.onended = finish;
      audio.onerror = function () { finish(); speak(button.getAttribute("data-say")); };
      audio.play().catch(function () { finish(); speak(button.getAttribute("data-say")); });
      return;
    }
    speak(button.getAttribute("data-say"), finish);
  }

  function speak(text, done) {
    if (!synth || !text) { if (done) done(); return; }
    synth.cancel();
    var u = new SpeechSynthesisUtterance(text);
    u.lang = "te-IN";
    var v = teluguVoice();
    if (v) u.voice = v;
    u.rate = slow ? 0.6 : 0.9;
    u.onend = u.onerror = function () { if (done) done(); };
    synth.speak(u);
  }

  function strip(s) { return (s || "").replace(/[\s.,?!।]+/g, "").normalize("NFC"); }

  function close(a, b) {  // same letters, allowing one slip, for a quick friendly signal only
    a = strip(a); b = strip(b);
    if (!a || !b) return false;
    if (a === b) return true;
    if (Math.abs(a.length - b.length) > 1) return false;
    var i = 0, j = 0, miss = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++miss > 1) return false;
      if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++; }
    }
    return miss + (a.length - i) + (b.length - j) <= 1;
  }

  function listen(button) {
    var out = document.getElementById(button.getAttribute("data-out"));
    var rec = new Rec();
    rec.lang = "te-IN"; rec.maxAlternatives = 3; rec.interimResults = false;
    button.classList.add("is-listening");
    rec.onresult = function (ev) {
      var heard = ev.results[0][0].transcript, ok = false, k;
      for (k = 0; k < ev.results[0].length; k++) { if (close(ev.results[0][k].transcript, button.getAttribute("data-expect"))) ok = true; }
      if (out) {
        out.textContent = button.getAttribute("data-heard") + " ";
        var span = document.createElement("span"); span.lang = "te"; span.textContent = heard; out.appendChild(span);
        out.appendChild(document.createTextNode(" — " + button.getAttribute(ok ? "data-close" : "data-again")));
        out.className = "say-out " + (ok ? "is-close" : "is-off");
      }
    };
    rec.onerror = rec.onend = function () { button.classList.remove("is-listening"); };
    try { rec.start(); } catch (e) { button.classList.remove("is-listening"); }
  }

  function init() {
    var canSpeak = !!synth || !!document.querySelector(".speak[data-audio]");
    [].forEach.call(document.querySelectorAll(".speak"), function (b) {
      if (!canSpeak) return;
      b.hidden = false;
      b.addEventListener("click", function () { say(b); });
    });
    [].forEach.call(document.querySelectorAll(".say-it"), function (b) {
      if (!Rec) return;
      b.hidden = false;
      b.addEventListener("click", function () { listen(b); });
    });
    [].forEach.call(document.querySelectorAll(".slow-toggle"), function (b) {
      if (!canSpeak) return;
      b.hidden = false;
      b.setAttribute("aria-pressed", slow ? "true" : "false");
      b.addEventListener("click", function () {
        slow = !slow;
        try { window.localStorage.setItem("setu.slow", slow ? "1" : "0"); } catch (e) { /* ignore */ }
        [].forEach.call(document.querySelectorAll(".slow-toggle"), function (x) { x.setAttribute("aria-pressed", slow ? "true" : "false"); });
      });
    });
  }

  if (synth && synth.onvoiceschanged !== undefined) synth.onvoiceschanged = function () {};
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
