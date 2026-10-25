/* PharmaGarde Douala — améliorations progressives (l'application fonctionne aussi sans JavaScript). */
(function () {
  "use strict";
  var $ = function (sel, root) { return (root || document).querySelector(sel); };
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var debounce = function (fn, ms) { var t; return function () { var a = arguments, c = this; clearTimeout(t); t = setTimeout(function () { fn.apply(c, a); }, ms); }; };

  /* Afficher / masquer un mot de passe */
  $$("[data-toggle-password]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var input = btn.parentElement.querySelector("input");
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.setAttribute("aria-label", show ? "Masquer le mot de passe" : "Afficher le mot de passe");
    });
  });

  /* Fermer un message de confirmation */
  $$("[data-dismiss]").forEach(function (btn) {
    btn.addEventListener("click", function () { var t = btn.closest("[data-toast]"); if (t) { t.remove(); } });
  });

  /* Confirmation avant une action destructrice */
  $$("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (e) { if (!window.confirm(el.getAttribute("data-confirm"))) { e.preventDefault(); } });
  });

  /* Sélecteur de quartier : accueil = filtre les gardes ; ailleurs = relance la recherche */
  $$("[data-quartier]").forEach(function (sel) {
    sel.addEventListener("change", function () {
      var form = sel.closest("form");
      var home = form && form.getAttribute("data-home-url");
      if (home) {
        window.location.href = home + (sel.value ? "?quartier=" + encodeURIComponent(sel.value) : "");
      } else if (form) { form.submit(); }
    });
  });
  $$("[data-quartier-side]").forEach(function (sel) {
    sel.addEventListener("change", function () { sel.closest("form").submit(); });
  });
  $$("[data-autosubmit]").forEach(function (form) {
    $$("select", form).forEach(function (s) { s.addEventListener("change", function () { form.submit(); }); });
  });

  /* Fenêtres modales : Échap ou clic sur le fond = fermer, focus sur le premier champ */
  var modal = $("[data-modal]");
  if (modal) {
    var close = $("[data-modal-close]", modal);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && close) { window.location.href = close.href; } });
    modal.addEventListener("mousedown", function (e) { if (e.target === modal && close) { window.location.href = close.href; } });
    var first = $("input:not([type=hidden]):not([disabled]):not(.visually-hidden), select", modal);
    if (first) { first.focus(); }
  }

  /* Suggestions de médicaments (page Médicaments) */
  var sform = $("[data-suggest-url]");
  if (sform) {
    var list = $("[data-suggestion-list]", sform);
    var input = $("[data-med-input]", sform);
    var quartier = $("[data-quartier-mirror]", sform);
    var frequents = list ? list.innerHTML : "";
    var run = debounce(function () {
      var q = input.value.trim();
      if (q.length < 2) { list.innerHTML = frequents; return; }
      fetch(sform.getAttribute("data-suggest-url") + "?q=" + encodeURIComponent(q), { headers: { Accept: "application/json" } })
        .then(function (r) { return r.json(); })
        .then(function (json) {
          list.textContent = "";
          if (!json.data.length) {
            var li = document.createElement("li");
            li.className = "catalogue-empty muted";
            li.textContent = "Aucune suggestion. Lancez la recherche pour vérifier.";
            list.appendChild(li); return;
          }
          json.data.forEach(function (m) {
            var li = document.createElement("li"), a = document.createElement("a");
            a.className = "suggestion";
            a.href = "/medicaments?m=" + m.id + (quartier && quartier.value ? "&quartier=" + encodeURIComponent(quartier.value) : "");
            var t = document.createElement("span"); t.className = "suggestion-text";
            var s = document.createElement("strong"); s.textContent = m.nom;
            var d = document.createElement("span"); d.className = "muted"; d.textContent = m.dosage + " · " + m.forme;
            t.appendChild(s); t.appendChild(d); a.appendChild(t); li.appendChild(a); list.appendChild(li);
          });
        }).catch(function () { /* silencieux : le formulaire reste utilisable */ });
    }, 220);
    input.addEventListener("input", run);
  }

  /* Recherche en direct dans la fenêtre « Ajouter un médicament » (fragment HTML rendu par le serveur) */
  var cform = $("[data-catalogue-form]");
  if (cform) {
    var cin = $("[data-catalogue-input]", cform);
    var clist = $("[data-catalogue-list]");
    if (cin && clist) {
      cin.addEventListener("input", debounce(function () {
        var url = cform.getAttribute("data-partial-url") + "&q_med=" + encodeURIComponent(cin.value.trim());
        fetch(url, { headers: { "X-Requested-With": "fetch" } })
          .then(function (r) { return r.text(); })
          .then(function (html) { clist.innerHTML = html; })
          .catch(function () {});
      }, 220));
    }
  }

  /* Import CSV : choix du fichier ou glisser-déposer => analyse automatique */
  var iform = $("[data-import-form]");
  if (iform) {
    var fin = $("[data-file-input]", iform), name = $("[data-file-name]", iform), dz = $("[data-dropzone]", iform);
    var send = function () { if (fin.files.length) { name.textContent = fin.files[0].name; iform.submit(); } };
    fin.addEventListener("change", send);
    ["dragenter", "dragover"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("is-over"); }); });
    ["dragleave", "drop"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("is-over"); }); });
    dz.addEventListener("drop", function (e) { if (e.dataTransfer.files.length) { fin.files = e.dataTransfer.files; send(); } });
  }

  /* Planning : contrôle en direct du chevauchement (règle R2) — le serveur re-vérifie toujours */
  var gform = $("[data-garde-form]");
  if (gform) {
    var save = $("[data-save]", gform), zone = $("[data-conflit]", gform);
    var psel = $("[data-pharmacie-select]", gform), hint = $("[data-pharmacie-hint]", gform);
    var token = $("input[name=csrf_token]", gform).value;
    var fields = $$("input[data-g-field], select", gform);
    var show = function (cls, text, extra) {
      zone.textContent = "";
      if (!text) { return; }
      var a = document.createElement("div"); a.className = "alert " + cls; a.setAttribute("role", "alert");
      var s = document.createElement("span"); s.textContent = text; a.appendChild(s); zone.appendChild(a);
      if (extra) { var p = document.createElement("p"); p.className = "text-red strong"; p.textContent = extra; zone.appendChild(p); }
    };
    var check = debounce(function () {
      var fd = new FormData(gform);
      if (gform.getAttribute("data-garde-id")) { fd.append("garde_id", gform.getAttribute("data-garde-id")); }
      fetch(gform.getAttribute("data-check-url"), { method: "POST", body: fd, headers: { "X-CSRF-Token": token } })
        .then(function (r) { return r.json(); })
        .then(function (json) {
          var d = json.data;
          if (d.valide) { show(); save.classList.remove("is-disabled"); return; }
          if (d.message) { show("alert-red", d.message, d.creneau); save.classList.add("is-disabled"); }
          else { show(); save.classList.remove("is-disabled"); }
        }).catch(function () {});
    }, 300);
    fields.forEach(function (f) { f.addEventListener("change", check); });
    if (psel && hint) {
      psel.addEventListener("change", function () {
        var o = psel.options[psel.selectedIndex];
        hint.textContent = o && o.getAttribute("data-quartier") ? o.getAttribute("data-quartier") + " · Pharmacie active" : "";
      });
    }
    gform.addEventListener("submit", function (e) { if (save.classList.contains("is-disabled") && !zone.querySelector(".alert")) { save.classList.remove("is-disabled"); } });
  }
})();
