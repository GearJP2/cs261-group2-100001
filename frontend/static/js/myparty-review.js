(() => {
  document.querySelectorAll('[data-review-dialog]').forEach(dialog => {
    const form = dialog.querySelector('form');
    const target = form.elements.reviewee_id;
    const comment = form.elements.comment;
    const message = dialog.querySelector('[data-review-message]');
    const close = dialog.querySelector('[data-review-close]');
    const submit = form.querySelector('[type="submit"]');
    const opener = document.querySelector(`[data-open-review="${dialog.id}"]`);
    let pending = false;
    opener.addEventListener('click', () => { message.textContent = ''; dialog.showModal(); });
    close.addEventListener('click', () => dialog.close());
    dialog.addEventListener('cancel', event => { if (pending) event.preventDefault(); });
    dialog.addEventListener('close', () => {
      if (!opener.disabled) opener.focus();
      else document.getElementById('history-heading').focus();
    });
    comment.addEventListener('input', () => {
      dialog.querySelector('[data-review-count]').textContent = String(comment.value.length);
      comment.setCustomValidity('');
    });
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (pending) return;
      comment.setCustomValidity(comment.value.trim() ? '' : 'กรุณาระบุความคิดเห็น');
      if (!form.reportValidity()) return;
      const selected = target.selectedOptions[0];
      const payload = { reviewee_id: Number(target.value), rating: Number(form.elements.rating.value), comment: comment.value.trim() };
      pending = true;
      submit.disabled = close.disabled = true;
      target.disabled = comment.disabled = true;
      form.querySelectorAll('[name="rating"]').forEach(node => { node.disabled = true; });
      message.textContent = 'กำลังส่งรีวิว…';
      try {
        await window.UniSport.request(`/parties/${dialog.dataset.partyId}/reviews`, { method: 'POST', body: JSON.stringify(payload) });
        selected.disabled = true;
        selected.textContent += ' — รีวิวแล้ว';
        message.textContent = 'บันทึกรีวิวเรียบร้อยแล้ว';
        form.reset();
        dialog.querySelector('[data-review-count]').textContent = '0';
      } catch (error) {
        if (error.status === 409 && error.payload?.error?.code === 'REVIEW_EXISTS') {
          selected.disabled = true;
          selected.textContent += ' — รีวิวแล้ว';
          target.value = '';
        }
        message.textContent = error.status ? error.message : 'ยังยืนยันผลส่งรีวิวไม่ได้ กรุณาโหลดหน้าใหม่เพื่อตรวจสถานะก่อนส่งอีกครั้ง';
      } finally {
        pending = false;
        close.disabled = false;
        target.disabled = comment.disabled = false;
        form.querySelectorAll('[name="rating"]').forEach(node => { node.disabled = false; });
        const available = [...target.options].some(option => option.value && !option.disabled);
        submit.disabled = !available;
        opener.disabled = !available;
        if (!available) opener.textContent = 'รีวิวสมาชิกครบแล้ว';
      }
    });
  });
})();
