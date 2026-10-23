let installPrompt = null;
window.addEventListener('beforeinstallprompt', event => {
  event.preventDefault(); installPrompt = event;
  const button = document.getElementById('install-btn');
  if (button) button.hidden = false;
});
document.getElementById('install-btn')?.addEventListener('click', async () => {
  if (!installPrompt) return;
  await installPrompt.prompt(); await installPrompt.userChoice;
  installPrompt = null; document.getElementById('install-btn').hidden = true;
});
if ('serviceWorker' in navigator) window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
const menu = document.getElementById('mobile-menu');
const sidebar = document.getElementById('sidebar');
const overlay = document.getElementById('menu-overlay');
function closeMenu() {
  sidebar?.classList.remove('open'); overlay?.classList.remove('open');
  menu?.setAttribute('aria-expanded', 'false');
}
menu?.addEventListener('click', () => {
  const open = sidebar?.classList.toggle('open');
  overlay?.classList.toggle('open', Boolean(open));
  menu.setAttribute('aria-expanded', String(Boolean(open)));
});
overlay?.addEventListener('click', closeMenu);
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
document.querySelectorAll('form[data-confirm]').forEach(form => form.addEventListener('submit', event => {
  if (!window.confirm(form.dataset.confirm)) event.preventDefault();
}));
const expenseForm = document.querySelector('[data-expense-form]');
if (expenseForm) {
  const category = expenseForm.querySelector('[name="category"]');
  const title = expenseForm.querySelector('[name="title"]');
  const tabs = document.querySelectorAll('[data-expense-category]');
  function updateCategory() {
    const group = ['fuel', 'maintenance'].includes(category.value) ? category.value : 'other';
    tabs.forEach(tab => {
      const active = tab.dataset.expenseCategory === group;
      tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active));
    });
    ['liters', 'price_per_liter', 'fuel_type'].forEach(name => {
      const field = expenseForm.querySelector(`[data-field="${name}"]`);
      if (field) {
        field.hidden = group !== 'fuel';
        field.querySelectorAll('input, select').forEach(input => { input.disabled = group !== 'fuel'; });
      }
    });
    const categoryField = expenseForm.querySelector('[data-field="category"]');
    if (categoryField) categoryField.hidden = group !== 'other';
    if (title && ['', 'Fuel refill', 'Maintenance service', 'Other expense'].includes(title.value)) {
      title.value = group === 'fuel' ? 'Fuel refill' : group === 'maintenance' ? 'Maintenance service' : 'Other expense';
    }
    const pumpLabel = expenseForm.querySelector('[data-field="pump_photo"] > label');
    if (pumpLabel) pumpLabel.textContent = group === 'maintenance' ? 'Service / maintenance photo' : 'Pump display photo';
  }
  tabs.forEach(tab => tab.addEventListener('click', () => { category.value = tab.dataset.expenseCategory; updateCategory(); }));
  category?.addEventListener('change', updateCategory);
  if (category) updateCategory();
  document.querySelector('[data-calculate-fuel]')?.addEventListener('click', () => {
    const liters = Number(expenseForm.querySelector('[name="liters"]').value);
    const price = Number(expenseForm.querySelector('[name="price_per_liter"]').value);
    const status = document.querySelector('[data-calculation-status]');
    const total = liters * price;
    if (!Number.isFinite(total) || liters <= 0 || price <= 0 || total > 9999999999.99) {
      status.textContent = 'Enter a positive quantity and price per litre, then calculate the total.'; return;
    }
    expenseForm.querySelector('[name="amount"]').value = total.toFixed(2);
    status.textContent = `Total updated to ৳ ${total.toFixed(2)}. Check it against your receipt before saving.`;
  });
}
document.querySelectorAll('[data-camera], [data-library]').forEach(button => button.addEventListener('click', () => {
  const input = document.getElementById(button.dataset.camera || button.dataset.library);
  if (!input) return;
  input.setAttribute('accept', 'image/*');
  if (button.hasAttribute('data-camera')) input.setAttribute('capture', 'environment');
  else input.removeAttribute('capture');
  input.click();
}));
document.querySelectorAll('input[type="file"]').forEach(input => {
  let previewUrl = null;
  input.addEventListener('change', () => {
    const preview = input.closest('.photo-upload')?.querySelector('.photo-preview');
    if (!preview) return;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const file = input.files?.[0]; preview.hidden = !file || !file.type.startsWith('image/');
    if (!preview.hidden) { previewUrl = URL.createObjectURL(file); preview.src = previewUrl; }
    else preview.removeAttribute('src');
  });
});
window.addEventListener('load', () => {
  const charts = document.querySelectorAll('#trendChart, #categoryChart');
  if (!window.Chart) {
    charts.forEach(canvas => {
      canvas.hidden = true;
      const message = document.createElement('p'); message.className = 'chart-message';
      message.textContent = 'Connect to the internet to load this chart. Your expense totals remain available.';
      canvas.parentNode.appendChild(message);
    }); return;
  }
  document.querySelectorAll('[data-chart-fallback]').forEach(element => { element.hidden = true; });
  Chart.defaults.color = '#9aa3af'; Chart.defaults.font.family = 'DM Sans, sans-serif';
  charts.forEach(canvas => {
    let rows; try { rows = JSON.parse(canvas.dataset.values); } catch { return; }
    if (!rows.length || !rows.some(row => Number(row.value) > 0)) {
      canvas.hidden = true;
      const message = document.createElement('p'); message.className = 'chart-message';
      message.textContent = 'Your next expense will bring this chart to life.'; canvas.parentNode.appendChild(message); return;
    }
    const trend = canvas.id === 'trendChart'; const context = canvas.getContext('2d');
    const gradient = context.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(255,52,62,.30)'); gradient.addColorStop(1, 'rgba(255,52,62,0)');
    const reportLegend = Boolean(canvas.closest('.breakdown-layout'));
    new Chart(context, {
      type: trend ? 'line' : 'doughnut',
      data: {labels: rows.map(row => row.label), datasets: [{data: rows.map(row => row.value),
        backgroundColor: trend ? gradient : ['#ff343e','#ffb07c','#219fd5','#6786ab','#9c83db','#6ac9a5','#ddb760'],
        borderColor: trend ? '#ff343e' : '#080b0e', borderWidth: trend ? 2.5 : 2,
        fill: trend, tension: .42, pointRadius: rows.length === 1 ? 4 : 0, hoverOffset: trend ? 0 : 5}]},
      options: {responsive: true, maintainAspectRatio: false, cutout: '69%',
        plugins: {legend: {display: !trend && !reportLegend, position: 'right', labels: {boxWidth: 8, padding: 12, font: {size: 10}}}},
        ...(trend ? {scales: {
          x: {grid: {display: false}, border: {display: false}, ticks: {maxTicksLimit: 6, font: {size: 9}}},
          y: {beginAtZero: true, grid: {color: '#252b323d'}, border: {display: false}, ticks: {maxTicksLimit: 4, font: {size: 9}, callback: value => value >= 1000 ? `৳ ${value / 1000}k` : `৳ ${value}`}}
        }} : {})}
    });
  });
});
