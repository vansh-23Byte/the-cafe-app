/* Basket page: render lines, adjust quantities, submit the order. */

document.addEventListener('DOMContentLoaded', () => {
  const linesEl = document.getElementById('lines');
  const liveEl = document.getElementById('basket-live');
  const emptyEl = document.getElementById('basket-empty');
  const receiptEl = document.getElementById('receipt');
  const errorEl = document.getElementById('checkout-error');
  const form = document.getElementById('checkout');
  let placed = false;

  function render() {
    if (placed) return;
    const lines = Basket.read();
    const has = lines.length > 0;
    liveEl.hidden = !has;
    emptyEl.hidden = has;

    linesEl.innerHTML = '';
    lines.forEach((line) => {
      const row = document.createElement('div');
      row.className = 'cart-line';
      row.innerHTML = `
        <div>
          <h3 style="margin:0 0 .15rem;font-size:1.05rem"></h3>
          <p style="margin:0;color:var(--muted);font-size:.9rem">${money(line.price)} each</p>
        </div>
        <div class="qty">
          <button type="button" data-minus aria-label="One fewer">&minus;</button>
          <span>${line.qty}</span>
          <button type="button" data-plus aria-label="One more">+</button>
        </div>
        <strong>${money(line.price * line.qty)}</strong>`;
      row.querySelector('h3').textContent = line.name;
      row.querySelector('[data-minus]').addEventListener('click', () => Basket.setQty(line.id, line.qty - 1));
      row.querySelector('[data-plus]').addEventListener('click', () => Basket.setQty(line.id, line.qty + 1));
      linesEl.appendChild(row);
    });

    document.querySelectorAll('[data-total]').forEach((el) => {
      el.textContent = money(Basket.total());
    });
  }

  document.addEventListener('basket:change', render);
  document.querySelector('[data-clear]').addEventListener('click', () => Basket.clear());
  render();

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.hidden = true;

    const button = form.querySelector('button[type=submit]');
    button.disabled = true;
    button.textContent = 'Sending';

    try {
      const response = await fetch('/api/order', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items: Basket.read().map((line) => ({ id: line.id, qty: line.qty })),
          customer: form.customer.value,
          phone: form.phone.value,
          fulfilment: form.fulfilment.value,
          note: form.note.value
        })
      });
      const data = await response.json();

      if (!response.ok || !data.ok) {
        errorEl.textContent = data.error || 'The order did not go through. Try once more.';
        errorEl.hidden = false;
        return;
      }

      document.querySelector('[data-ref]').textContent = data.reference;
      document.querySelector('[data-eta]').textContent =
        `${money(data.total)} to pay at the counter. Ready in about ten minutes.`;
      placed = true;
      Basket.clear();
      liveEl.hidden = true;
      emptyEl.hidden = true;
      receiptEl.hidden = false;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      errorEl.textContent = 'No connection to the cafe. Check your network and try again.';
      errorEl.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = 'Place order';
    }
  });
});
