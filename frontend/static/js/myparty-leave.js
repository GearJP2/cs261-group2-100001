(() => {
  const pane = document.getElementById('grid-joined');
  const dialog = document.getElementById('leave-dialog');
  if (!pane || !dialog) return;
  const form = dialog.querySelector('form');
  const message = dialog.querySelector('[data-leave-message]');
  const close = dialog.querySelector('[data-leave-close]');
  const confirm = dialog.querySelector('[data-leave-confirm]');
  const refresh = dialog.querySelector('[data-leave-refresh]');
  function requireLogin() {
    document.querySelectorAll('[data-joined-party], [data-member-list], [data-party-members], [data-member-count], [data-party-count], [data-remaining-slots], [data-party-slots]').forEach(node => node.remove());
    document.getElementById('grid-created')?.replaceChildren();
    document.getElementById('grid-history')?.replaceChildren();
    window.location.replace('/login/');
  }
  let opener = null;
  let card = null;
  let pending = false;
  let finished = false;
  pane.querySelectorAll('[data-leave-party]').forEach(button => {
    button.addEventListener('click', () => {
      if (pending || button.disabled) return;
      opener = button;
      card = button.closest('[data-joined-party]');
      finished = false;
      refresh.hidden = true;
      confirm.hidden = false;
      confirm.disabled = false;
      close.textContent = 'ยกเลิก';
      message.textContent = '';
      dialog.querySelector('[data-leave-title]').textContent = card.querySelector('h3').textContent;
      dialog.showModal();
    });
  });
  close.addEventListener('click', () => dialog.close());
  refresh.addEventListener('click', () => window.location.reload());
  dialog.addEventListener('cancel', event => { if (pending) event.preventDefault(); });
  dialog.addEventListener('close', () => {
    if (opener?.isConnected && !opener.disabled) opener.focus();
    else document.getElementById('joined-heading').focus();
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (pending || finished || !opener) return;
    const partyId = opener.dataset.leaveParty;
    const submittedCard = card;
    const triggerBtn = opener;
    pending = true;
    confirm.disabled = close.disabled = triggerBtn.disabled = true;
    message.textContent = 'กำลังถอนตัว…';
    try {
      await window.UniSport.request(`/parties/${partyId}/leave`, { method: 'POST', body: '{}' });
      finished = true;
      const membersRefresh = await window.PartyMembers.refresh(partyId);
      if (membersRefresh.status === 'unauthorized') return;
      submittedCard.remove();
      pane.querySelector('[data-joined-empty]').hidden = Boolean(pane.querySelector('[data-joined-party]'));
      // ล้างรายชื่อสมาชิกของกิจกรรมที่ถอนตัวแล้ว (กรณีแสดงร่วมกับ Members UI #77/#78)
      document.querySelectorAll(`[data-party-members="${partyId}"], [data-party-id="${partyId}"] [data-member-list], [data-joined-party="${partyId}"] [data-member-list]`).forEach(el => {
        el.innerHTML = '';
        el.hidden = true;
      });
      let result = 'ถอนตัวสำเร็จแล้ว';
      if (membersRefresh.status === 'error') result += ' แต่โหลดรายชื่อสมาชิกไม่ได้';
      try {
        const detail = await window.UniSport.request(`/parties/${partyId}`);
        result += ` สมาชิกปัจจุบัน ${detail.member_count} คน ที่ว่าง ${detail.remaining_slots} ที่`;
        const countNode = document.querySelector(`[data-party-count="${partyId}"], [data-party-id="${partyId}"] [data-member-count]`);
        if (countNode) countNode.textContent = String(detail.member_count);
        const slotsNode = document.querySelector(`[data-party-slots="${partyId}"], [data-party-id="${partyId}"] [data-remaining-slots]`);
        if (slotsNode) slotsNode.textContent = String(detail.remaining_slots);
      } catch (detailError) {
        if (detailError.status === 401) { requireLogin(); return; }
        if (detailError.status === 403) {
          result += ' (คุณไม่มีสิทธิ์ดูรายชื่อสมาชิกของกิจกรรมนี้อีกต่อไป)';
        } else {
          result += ' แต่โหลดข้อมูลล่าสุดไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจจำนวนสมาชิก';
        }
      }
      message.textContent = result;
      pane.querySelector('[data-leave-result]').textContent = result;
    } catch (error) {
      if (error.status === 401) { requireLogin(); return; }
      if (error.status === 403) {
        message.textContent = error.message || 'คุณไม่มีสิทธิ์ดำเนินการ หรือเซสชันหมดอายุ ระบบได้ซ่อนข้อมูลสมาชิกแล้ว';
        // 403 กระทบเฉพาะกิจกรรมนี้; 401 ล้างทุกส่วนก่อนกลับไปล็อกอิน
        submittedCard?.querySelectorAll('[data-member-list], [data-party-members], .member-list').forEach(el => {
          el.innerHTML = '';
          el.hidden = true;
        });
        document.querySelectorAll(`[data-party-members="${partyId}"], [data-party-id="${partyId}"] [data-member-list], [data-joined-party="${partyId}"] [data-member-list]`).forEach(el => {
          el.innerHTML = '';
          el.hidden = true;
        });
        const countEl = submittedCard?.querySelector('[data-joined-count]');
        if (countEl) countEl.textContent = '-';
        pane.querySelector('[data-leave-result]').textContent = message.textContent;
      } else if (error.status === 409) {
        message.textContent = error.message || 'ไม่สามารถถอนตัวได้เนื่องจากสถานะกิจกรรมเปลี่ยนไปแล้ว';
        pane.querySelector('[data-leave-result]').textContent = message.textContent;
      } else {
        message.textContent = error.status
          ? error.message
          : 'ยังยืนยันผลถอนตัวไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจสถานะ ห้ามถือว่าถอนตัวสำเร็จแล้ว';
        message.textContent += ' กรุณาโหลดสถานะล่าสุดเพื่อตรวจผลก่อนดำเนินการอีกครั้ง';
      }
      // Old commands must not be retried across a reapproval cycle.
      confirm.hidden = true;
      refresh.hidden = false;
    } finally {
      pending = false;
      close.disabled = false;
      close.textContent = 'ปิด';
      if (finished) confirm.hidden = true;
      close.focus();
    }
  });
})();
