/* Admin fleet usage live refresh (residual peers + package store). CSP: 'self'. */
(function () {
  var root = document.getElementById("admin-node-usage");
  if (!root) return;
  var api =
    root.getAttribute("data-fleet-usage-api") || "/admin/api/fleet-usage";
  var ms = parseInt(root.getAttribute("data-fleet-refresh-ms") || "5000", 10);
  if (!ms || ms < 2000) ms = 5000;
  var stamp = document.getElementById("admin-node-usage-refreshed");
  function setText(id, text) {
    var el = document.getElementById(id);
    if (el) el.textContent = text == null ? "—" : String(text);
  }
  function applyRow(r) {
    if (!r || !r.code) return;
    var c = r.code;
    setText("admin-node-bw-used-" + c, r.bandwidth_used_display);
    setText("admin-node-bw-cap-" + c, r.bandwidth_cap_display);
    setText("admin-node-bw-util-" + c, r.bandwidth_util_display);
    setText("admin-node-bytes-" + c, r.bytes_relayed_display);
    setText("admin-node-sess-" + c, r.sessions_display);
    var st = document.getElementById("admin-node-status-" + c);
    if (st) {
      st.textContent = r.status || "unknown";
      st.className = "badge " + (r.status === "ok" ? "ok" : "bad");
    }
    setText("admin-node-detail-" + c, r.detail || "");
  }
  function applyPackageHost(r) {
    if (!r || !r.id) return;
    var id = r.id;
    setText("admin-pkg-label-" + id, r.label);
    setText("admin-pkg-host-" + id, r.host);
    setText("admin-pkg-load-" + id, r.load_display);
    setText("admin-pkg-disk-used-" + id, r.disk_used_display);
    setText("admin-pkg-disk-total-" + id, r.disk_total_display);
    setText("admin-pkg-disk-avail-" + id, r.disk_avail_display);
    setText("admin-pkg-disk-util-" + id, r.disk_util_display);
    setText("admin-pkg-uptime-" + id, r.uptime_display);
    var st = document.getElementById("admin-pkg-status-" + id);
    if (st) {
      st.textContent = r.status || "unknown";
      st.className = "badge " + (r.status === "ok" ? "ok" : "bad");
    }
    setText("admin-pkg-detail-" + id, r.detail || "");
  }
  function tick() {
    fetch(api, {
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
        if (data.rows) data.rows.forEach(applyRow);
        if (data.package_hosts) data.package_hosts.forEach(applyPackageHost);
        if (stamp)
          stamp.textContent = "last refresh " + (data.refreshed_at || "—");
        if (data.refresh_ms && data.refresh_ms >= 2000) ms = data.refresh_ms;
      })
      .catch(function () {
        if (stamp) stamp.textContent = "refresh failed (will retry)";
      });
  }
  setInterval(tick, ms);
  setTimeout(tick, Math.min(1500, ms));
})();
