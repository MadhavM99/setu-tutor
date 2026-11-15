/* SETU match game: one-to-one pairing on top of plain radio buttons. Without this file the form still works and
   the server checks that every word has an answer. With it: an answer used for one word is taken off any other
   word, a live count shows progress, and the check button waits until every word has an answer. */
(function () {
  "use strict";
  var DIG = "०१२३४५६७८९";
  function dev(n) { return String(n).replace(/[0-9]/g, function (d) { return DIG[+d]; }); }
  [].forEach.call(document.querySelectorAll("form[data-match]"), function (form) {
    var total = +form.getAttribute("data-total"), tpl = form.getAttribute("data-template");
    var counter = form.querySelector("[data-count]"), check = form.querySelector("[data-check]");
    function update() {
      var picked = {}, n = 0;
      [].forEach.call(form.querySelectorAll("input[type=radio]:checked"), function (r) { picked[r.name] = r.value; n++; });
      [].forEach.call(form.querySelectorAll("input[type=radio]"), function (r) {
        var usedElsewhere = false;
        for (var k in picked) { if (k !== r.name && picked[k] === r.value) usedElsewhere = true; }
        r.parentNode.classList.toggle("is-used", usedElsewhere);
      });
      if (counter) counter.textContent = tpl.replace("§1", dev(n)).replace("§2", dev(total));
      if (check) check.disabled = n < total;
      [].forEach.call(form.querySelectorAll(".match-row"), function (row) {
        row.classList.toggle("is-answered", !!row.querySelector("input:checked"));
      });
    }
    form.addEventListener("change", function (ev) {
      var t = ev.target;
      if (t && t.type === "radio") {  // one answer, one word: free it from any other word
        [].forEach.call(form.querySelectorAll("input[type=radio]:checked"), function (r) {
          if (r !== t && r.value === t.value) r.checked = false;
        });
      }
      update();
    });
    update();
  });
})();
