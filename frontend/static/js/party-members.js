(() => {
  "use strict";

  const requestVersions = new Map();
  const retryBindings = new WeakSet();

  function panelsFor(partyId) {
    const id = String(partyId);
    return [...document.querySelectorAll("[data-party-members]")]
      .filter((panel) => panel.dataset.partyMembers === id);
  }

  function clearList(panel, message, canRetry = false) {
    panel.querySelector("[data-member-list]")?.replaceChildren();
    const status = panel.querySelector("[data-member-status]");
    if (status) status.textContent = message;
    const retry = panel.querySelector("[data-member-retry]");
    if (retry) retry.hidden = !canRetry;
  }

  function bindRetry(panel, partyId) {
    const retry = panel.querySelector("[data-member-retry]");
    if (!retry || retryBindings.has(retry)) return;
    retryBindings.add(retry);
    retry.addEventListener("click", () => refresh(partyId));
  }

  function validResponse(data) {
    return data
      && Array.isArray(data.members)
      && Number.isInteger(data.member_count)
      && data.member_count === data.members.length
      && data.members.every((member) => Number.isInteger(member.user_id)
        && typeof member.display_name === "string"
        && ["Host", "Member"].includes(member.role));
  }

  function render(panel, data) {
    const list = panel.querySelector("[data-member-list]");
    list.replaceChildren();
    data.members.forEach((member) => {
      const row = document.createElement("li");
      row.className = "mp-member-row";
      const name = document.createElement("span");
      name.className = "mp-member-name";
      name.textContent = member.display_name;
      const role = document.createElement("span");
      role.className = "mp-member-role";
      role.textContent = member.role === "Host" ? "ผู้จัด" : "สมาชิก";
      row.append(name, role);
      list.append(row);
    });

    const count = panel.querySelector("[data-member-count]");
    if (count) count.textContent = String(data.member_count);
    const capacity = Number(panel.dataset.partyCapacity);
    const remaining = panel.querySelector("[data-remaining-slots]");
    if (remaining && Number.isInteger(capacity)) {
      remaining.textContent = String(capacity - data.member_count);
    }
    const status = panel.querySelector("[data-member-status]");
    if (status) status.textContent = data.members.length ? "" : "ยังไม่มีสมาชิกปัจจุบัน";
    const retry = panel.querySelector("[data-member-retry]");
    if (retry) retry.hidden = true;
  }

  async function refresh(partyId) {
    const panels = panelsFor(partyId);
    if (!panels.length) return { status: "no-panel" };

    const id = String(partyId);
    const version = (requestVersions.get(id) || 0) + 1;
    requestVersions.set(id, version);
    panels.forEach((panel) => {
      bindRetry(panel, id);
      clearList(panel, "กำลังโหลดสมาชิก…");
    });

    try {
      const data = await window.UniSport.request(`/parties/${id}/members`);
      if (requestVersions.get(id) !== version) return { status: "stale" };
      if (!validResponse(data)) throw new Error("ข้อมูลรายชื่อสมาชิกไม่ถูกต้อง");
      panels.forEach((panel) => render(panel, data));
      return { status: "loaded", memberCount: data.member_count };
    } catch (error) {
      if (requestVersions.get(id) !== version) return { status: "stale" };
      if (error.status === 401) {
        panels.forEach((panel) => clearList(panel, ""));
        window.location.replace("/login/");
        return { status: "unauthorized" };
      }
      if (error.status === 403) {
        panels.forEach((panel) => clearList(
          panel,
          "รายชื่อสมาชิกแสดงได้เฉพาะผู้จัดหรือสมาชิกปัจจุบัน",
        ));
        return { status: "forbidden" };
      }
      panels.forEach((panel) => clearList(
        panel,
        "โหลดรายชื่อสมาชิกไม่สำเร็จ กรุณาลองอีกครั้ง",
        true,
      ));
      return { status: "error", error };
    }
  }

  window.PartyMembers = { refresh };

  document.addEventListener("DOMContentLoaded", () => {
    const ids = new Set([...document.querySelectorAll("[data-party-members]")]
      .map((panel) => panel.dataset.partyMembers));
    ids.forEach((id) => refresh(id));
  });
})();
