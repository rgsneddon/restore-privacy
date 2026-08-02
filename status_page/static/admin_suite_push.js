/* Admin UPLOADS Suite push: Helsinki job poll + client package selection. CSP: 'self'. */
(function () {
  var root = document.getElementById("admin-suite-push-upload");
  if (!root) return;
  var form = document.getElementById("admin-suite-push-form");
  var clientForm = document.getElementById("admin-client-push-form");
  var tbody = document.getElementById("admin-suite-packages-tbody");
  var table = document.getElementById("admin-suite-packages-table");
  var statusEl = document.getElementById("admin-suite-push-job-status");
  var btn = document.getElementById("admin-suite-push-btn");
  var jobApi =
    root.getAttribute("data-push-job-api") || "/admin/uploads/push-suite";
  var statusApi =
    root.getAttribute("data-push-status-api") ||
    "/admin/uploads/push-suite/status";
  var pollMs = 600;
  var pollTimer = null;
  var activeJobId = null;

  function selectedPackageBoxes() {
    var selected = document.querySelectorAll(
      'input.suite-pkg-checkbox[data-package-select="1"]:checked'
    );
    if (!selected.length) {
      selected = document.querySelectorAll(
        'input.suite-pkg-checkbox[form="admin-suite-push-form"]:checked'
      );
    }
    return selected;
  }

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text || "";
  }

  function applyRow(p) {
    if (!p || !p.filename || !tbody) return;
    var row = tbody.querySelector(
      'tr[data-filename="' + CSS.escape(p.filename) + '"]'
    );
    if (!row) return;
    var status = String(p.status || "pending");
    var progress = parseInt(p.progress, 10);
    if (isNaN(progress)) progress = 0;
    progress = Math.max(0, Math.min(100, progress));
    row.setAttribute("data-status", status);
    row.setAttribute("data-progress", String(progress));
    if (status === "done") {
      row.classList.add("suite-pkg-done");
    } else {
      row.classList.remove("suite-pkg-done");
    }
    var st = row.querySelector(".suite-pkg-status");
    if (st) {
      st.textContent = status;
      st.setAttribute("data-status", status);
    }
    var bar = row.querySelector(".suite-pkg-progress-bar");
    if (bar) bar.style.width = progress + "%";
    var wrap = row.querySelector(".suite-pkg-progress-wrap");
    if (wrap) wrap.setAttribute("aria-valuenow", String(progress));
    var pct = row.querySelector(".suite-pkg-progress-pct");
    if (pct) pct.textContent = progress + "%";
    if (p.present != null) {
      var loc = row.querySelector(".suite-pkg-local");
      if (loc) {
        var y = p.present ? "yes" : "no";
        loc.textContent = y;
        loc.setAttribute("data-present", y);
      }
    }
    if (p.staged != null) {
      var sg = row.querySelector(".suite-pkg-staged");
      if (sg) {
        var ys = p.staged ? "yes" : "no";
        sg.textContent = ys;
        sg.setAttribute("data-staged", ys);
      }
    }
  }

  function applyJob(job) {
    if (!job) return;
    var pkgs = job.packages || [];
    pkgs.forEach(applyRow);
    var done = job.done_count || 0;
    var total = job.total || pkgs.length || 0;
    var state = job.state || "";
    var msg = "Job " + (job.id || "") + " · " + state + " · " + done + "/" + total;
    if (job.message) msg += " · " + job.message;
    if (job.error) msg += " · " + job.error;
    setStatus(msg);
    if (state === "complete" || state === "failed") {
      stopPoll();
      if (btn) btn.disabled = false;
      if (state === "complete") {
        setStatus(msg + " · green done rows are finished");
      } else if (state === "failed" && job.error) {
        // Job-level failure (stage/SSH/etc.) — rows may stay pending; do not
        // treat every pending package as a per-file error.
        setStatus(msg + " · unstarted packages stay pending (see job error)");
      }
    }
  }

  function stopPoll() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  function pollOnce() {
    if (!activeJobId) return;
    var url =
      statusApi +
      (statusApi.indexOf("?") >= 0 ? "&" : "?") +
      "job_id=" +
      encodeURIComponent(activeJobId);
    fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
      cache: "no-store",
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function (data) {
        if (!data) return;
        var job = data.job || data;
        if (job && (job.missing_ssh_keys || job.message === "missing_ssh_keys")) {
          stopPoll();
          if (btn) btn.disabled = false;
          if (job.redirect) {
            setStatus(String(job.error || "SSH keys missing") + " — redirecting…");
            window.location.href = job.redirect;
            return;
          }
          setStatus(
            String(
              job.error ||
                data.error ||
                "SSH keys missing on status host — set RPT_SSH_KEY / RPT_SSH_PRIVATE_KEY or use Dry-run"
            )
          );
          applyJob(job);
          return;
        }
        if (!data.ok && !job) {
          if (data.error) setStatus(String(data.error));
          return;
        }
        applyJob(job);
      })
      .catch(function () {
        setStatus("status poll failed (will retry)");
      });
  }

  function startPoll(jobId) {
    activeJobId = jobId;
    stopPoll();
    pollOnce();
    pollTimer = setInterval(pollOnce, pollMs);
  }

  function setAllPackageChecks(mode) {
    // mode: "all" | "none" | "present"
    var boxes = document.querySelectorAll(
      'input.suite-pkg-checkbox[data-package-select="1"]'
    );
    boxes.forEach(function (box) {
      if (mode === "all") {
        box.checked = true;
      } else if (mode === "none") {
        box.checked = false;
      } else if (mode === "present") {
        var tr = box.closest("tr");
        var present =
          tr &&
          (tr.getAttribute("data-present") === "yes" ||
            (tr.querySelector(".suite-pkg-local") &&
              tr.querySelector(".suite-pkg-local").getAttribute("data-present") ===
                "yes"));
        box.checked = !!present;
      }
    });
  }
  var selPresent = document.getElementById("admin-suite-select-present");
  var selNone = document.getElementById("admin-suite-select-none");
  var selAll = document.getElementById("admin-suite-select-all");
  if (selPresent) selPresent.addEventListener("click", function () { setAllPackageChecks("present"); });
  if (selNone) selNone.addEventListener("click", function () { setAllPackageChecks("none"); });
  if (selAll) selAll.addEventListener("click", function () { setAllPackageChecks("all"); });

  if (form) {
    form.addEventListener("submit", function (ev) {
      if (!form.getAttribute("data-async-push")) return;
      ev.preventDefault();
      var selected = selectedPackageBoxes();
      if (!selected.length) {
        setStatus("Select at least one package checkbox before pushing.");
        return;
      }
      if (btn) btn.disabled = true;
      setStatus("Starting Suite Helsinki push for " + selected.length + " package(s)…");
      if (table) table.setAttribute("data-push-running", "1");
      var fd = new FormData(form);
      fd.set("async", "1");
      // Ensure package= values from table (form= attribute) are included
      selected.forEach(function (box) {
        if (box.name && box.value) {
          fd.append(box.name, box.value);
        }
      });
      fetch(jobApi, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: new URLSearchParams(fd),
      })
        .then(function (resp) {
          return resp.json().then(function (data) {
            return { status: resp.status, data: data };
          });
        })
        .then(function (res) {
          var data = res.data || {};
          if (data.missing_ssh_keys || data.redirect) {
            if (data.redirect) {
              setStatus(
                String(data.error || "SSH keys missing on status host") +
                  " — redirecting…"
              );
              window.location.href = data.redirect;
              return;
            }
            setStatus(
              String(
                data.error ||
                  "SSH keys missing — set RPT_SSH_KEY / RPT_SSH_PRIVATE_KEY on the status host, or enable Dry-run"
              )
            );
            if (data.job) applyJob(data.job);
            if (btn) btn.disabled = false;
            return;
          }
          if (!data.ok || !data.job_id) {
            setStatus(
              (data.error || "push start failed") +
                (res.status ? " (HTTP " + res.status + ")" : "")
            );
            if (btn) btn.disabled = false;
            return;
          }
          setStatus("Push job " + data.job_id + " running…");
          if (data.job) applyJob(data.job);
          startPoll(data.job_id);
        })
        .catch(function (err) {
          setStatus("Could not start push: " + (err && err.message ? err.message : "error"));
          if (btn) btn.disabled = false;
        });
    });
  }

  // Client-push: checkboxes use form="admin-client-push-form" so native POST
  // includes package= multi-values. Select helpers only enable matching rows.
  function clientPushBoxes() {
    return document.querySelectorAll(
      'input.client-push-pkg-checkbox[data-client-package-select="1"]'
    );
  }
  function setClientPushChecks(mode) {
    clientPushBoxes().forEach(function (box) {
      if (mode === "none") {
        box.checked = false;
        return;
      }
      // present / all → only matching (enabled) packages
      if (box.disabled) return;
      var match =
        box.getAttribute("data-package-match") === "yes" ||
        (box.closest("tr") &&
          box.closest("tr").getAttribute("data-match") === "yes");
      if (mode === "all" || mode === "present") {
        box.checked = !!match;
      }
    });
  }
  var cPresent = document.getElementById("admin-client-select-present");
  var cNone = document.getElementById("admin-client-select-none");
  var cAll = document.getElementById("admin-client-select-all");
  if (cPresent) cPresent.addEventListener("click", function () { setClientPushChecks("present"); });
  if (cNone) cNone.addEventListener("click", function () { setClientPushChecks("none"); });
  if (cAll) cAll.addEventListener("click", function () { setClientPushChecks("all"); });

  if (clientForm) {
    clientForm.addEventListener("submit", function (ev) {
      var section = document.getElementById("admin-client-push-section");
      if (section && section.getAttribute("data-can-push") === "0") {
        ev.preventDefault();
        setStatus(
          "Client push cannot be completed — no Suite packages match between " +
            "build host and Helsinki (or Helsinki is unknown)."
        );
        return;
      }
      // Collect selected matching packages (form= associates them with this form;
      // also inject hidden package= so submit works if form= is stripped).
      var selected = [];
      clientPushBoxes().forEach(function (box) {
        if (box.checked && box.value && !box.disabled) selected.push(box);
      });
      if (!selected.length) {
        ev.preventDefault();
        setStatus("Select at least one matching Suite package for client push.");
        return;
      }
      // Drop prior injected hiddens, then ensure package= values are on the form.
      var old = clientForm.querySelectorAll(
        'input[data-client-push-package-inject="1"]'
      );
      old.forEach(function (el) {
        if (el.parentNode) el.parentNode.removeChild(el);
      });
      selected.forEach(function (box) {
        // If checkbox already has form= association, native submit includes it.
        // Injecting duplicates can double-send — only inject when not form-linked
        // to this form id.
        var formAttr = box.getAttribute("form");
        if (formAttr === "admin-client-push-form" || clientForm.contains(box)) {
          return;
        }
        var hid = document.createElement("input");
        hid.type = "hidden";
        hid.name = "package";
        hid.value = box.value;
        hid.setAttribute("data-client-push-package-inject", "1");
        clientForm.appendChild(hid);
      });
    });
  }
})();
