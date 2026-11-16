(() => {
  const pane = document.getElementById('grid-joined');
  const dialog = document.getElementById('leave-dialog');
  const form = dialog.querySelector('form');
  const message = dialog.querySelector('[data-leave-message]');
  const close = dialog.querySelector('[data-leave-close]');
  const confirm = dialog.querySelector('[data-leave-confirm]');
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
      confirm.hidden = false;
      confirm.disabled = false;
      close.textContent = 'ยกเลิก';
      message.textContent = '';
      dialog.querySelector('[data-leave-title]').textContent = card.querySelector('h3').textContent;
      dialog.showModal();
    });
  });
  close.addEventListener('click', () => dialog.close());
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
    pending = true;
    confirm.disabled = close.disabled = true;
    message.textContent = 'กำลังถอนตัว…';
    try {
      await window.UniSport.request(`/parties/${partyId}/leave`, { method: 'POST', body: '{}' });
      finished = true;
      submittedCard.remove();
      pane.querySelector('[data-joined-empty]').hidden = Boolean(pane.querySelector('[data-joined-party]'));
      let result = 'ถอนตัวสำเร็จแล้ว';
      try {
        const detail = await window.UniSport.request(`/parties/${partyId}`);
        result += ` สมาชิกปัจจุบัน ${detail.member_count} คน ที่ว่าง ${detail.remaining_slots} ที่`;
      } catch (_) {
        result += ' แต่โหลดข้อมูลล่าสุดไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจจำนวนสมาชิก';
      }
      message.textContent = result;
      pane.querySelector('[data-leave-result]').textContent = result;
    } catch (error) {
      message.textContent = error.status ? error.message : 'ยังยืนยันผลถอนตัวไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจสถานะ ห้ามถือว่าถอนตัวสำเร็จแล้ว';
      // Old commands must not be retried across a reapproval cycle.
      confirm.hidden = true;
    } finally {
      pending = false;
      close.disabled = false;
      close.textContent = 'ปิด';
      if (finished) confirm.hidden = true;
      close.focus();
    }
  });
})();
