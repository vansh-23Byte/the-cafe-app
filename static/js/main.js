/* Shared behaviour: mobile nav, basket storage, add-to-basket buttons. */

const Basket = {
  KEY: 'pp-basket',

  read() {
    try {
      const raw = localStorage.getItem(this.KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (err) {
      return [];
    }
  },

  write(lines) {
    try {
      localStorage.setItem(this.KEY, JSON.stringify(lines));
    } catch (err) {
      /* storage can be unavailable; the basket then lasts only for this page */
    }
    this.paintCount();
    document.dispatchEvent(new CustomEvent('basket:change'));
  },

  add(item) {
    const lines = this.read();
    const found = lines.find((line) => line.id === item.id);
    if (found) {
      found.qty = Math.min(20, found.qty + 1);
    } else {
      lines.push({ id: item.id, name: item.name, price: item.price, qty: 1 });
    }
    this.write(lines);
  },

  setQty(id, qty) {
    const lines = this.read()
      .map((line) => (line.id === id ? { ...line, qty: Math.max(0, Math.min(20, qty)) } : line))
      .filter((line) => line.qty > 0);
    this.write(lines);
  },

  clear() { this.write([]); },

  count() { return this.read().reduce((sum, line) => sum + line.qty, 0); },

  total() { return this.read().reduce((sum, line) => sum + line.qty * line.price, 0); },

  paintCount() {
    const count = this.count();
    document.querySelectorAll('[data-basket-count]').forEach((el) => {
      el.textContent = count;
    });
  }
};

function money(value) {
  return '\u20b9' + Number(value).toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

document.addEventListener('DOMContentLoaded', () => {
  Basket.paintCount();

  const toggle = document.querySelector('.nav-toggle');
  const nav = document.getElementById('nav');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
  }

  document.querySelectorAll('[data-add]').forEach((button) => {
    button.addEventListener('click', () => {
      Basket.add({
        id: Number(button.dataset.add),
        name: button.dataset.name,
        price: Number(button.dataset.price)
      });
      const original = button.textContent;
      button.textContent = 'Added';
      setTimeout(() => { button.textContent = original; }, 1200);
    });
  });
});
