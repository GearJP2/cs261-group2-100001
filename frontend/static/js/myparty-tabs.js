(() => {
  const buttons = [...document.querySelectorAll('[data-myparty-tab]')];
  buttons.forEach(button => {
    const pane = document.getElementById(`grid-${button.dataset.mypartyTab}`);
    if (!pane) {
      button.disabled = true;
      button.title = 'ส่วนนี้ยังไม่พร้อมใช้งาน';
      return;
    }
    button.addEventListener('click', () => {
      buttons.forEach(other => {
        const active = other === button;
        other.classList.toggle('active', active);
        other.setAttribute('aria-pressed', String(active));
        const target = document.getElementById(`grid-${other.dataset.mypartyTab}`);
        if (target) target.hidden = !active;
      });
    });
  });
})();
