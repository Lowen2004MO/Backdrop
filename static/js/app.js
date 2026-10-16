document.addEventListener('DOMContentLoaded', () => {
  const button = document.querySelector('.menu-button');
  const nav = document.querySelector('#primary-nav');
  if (button && nav) button.addEventListener('click', () => {
    const open = button.getAttribute('aria-expanded') === 'true';
    button.setAttribute('aria-expanded', String(!open));
    nav.classList.toggle('open', !open);
  });
});

const filterDropdowns = '.period-dropdown, .question-picker';

document.addEventListener('click', (event) => {
  const closeButton = event.target.closest('[data-close-dropdown]');
  document.querySelectorAll(filterDropdowns).forEach(dropdown => {
    if (dropdown.open && (!dropdown.contains(event.target) || closeButton?.closest('details') === dropdown)) {
      dropdown.open = false;
      if (closeButton?.closest('details') === dropdown) dropdown.querySelector('summary').focus();
    }
  });
});

document.addEventListener('toggle', (event) => {
  const dropdown = event.target;
  if (!dropdown.matches(filterDropdowns) || !dropdown.open) return;
  document.querySelectorAll(filterDropdowns).forEach(other => {
    if (other !== dropdown) other.open = false;
  });
}, true);

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Escape') return;
  document.querySelectorAll(filterDropdowns).forEach(dropdown => {
    if (dropdown.open) {
      dropdown.open = false;
      dropdown.querySelector('summary').focus();
    }
  });
});

document.addEventListener('submit', (event) => {
  event.target.querySelectorAll(filterDropdowns).forEach(dropdown => { dropdown.open = false; });
}, true);

// Delegation keeps controls working after the dashboard form is replaced by HTMX.
document.addEventListener('change', (event) => {
  const input = event.target;
  const form = input.closest('form');
  if (!form) return;
  const recent = form.querySelector('[name=most_recent]');
  const allPeriods = form.querySelector('[name=all_periods]');
  const periods = [...form.querySelectorAll('input[name=period]')];
  const allGroups = form.querySelector('input[name=all_groups]');
  const groups = [...form.querySelectorAll('input[name=group]')];
  if (input === recent && recent.checked) {
    if (allPeriods) allPeriods.checked = false;
    periods.forEach((period, index) => { period.checked = index === periods.length - 1; });
  } else if (input === allPeriods && allPeriods.checked) {
    if (recent) recent.checked = false;
    periods.forEach(period => { period.checked = true; });
  } else if (input.name === 'period') {
    if (recent) recent.checked = false;
    if (allPeriods) allPeriods.checked = false;
  }
  if (input === allGroups && allGroups.checked) groups.forEach(group => { group.checked = false; });
  else if (input.name === 'group' && allGroups) allGroups.checked = false;
  form.querySelectorAll('.period-dropdown').forEach(dropdown => {
    const count = dropdown.querySelector('summary span');
    if (count) count.textContent = `${dropdown.querySelectorAll('input:checked').length} selected`;
  });
  if (input.matches('[data-change-question]')) {
    // Preserve the drill-down when changing questions within the same surveys.
    if (input.dataset.questionFamily !== form.dataset.questionFamily) {
      periods.forEach(period => { period.checked = false; });
      groups.forEach(group => { group.checked = false; });
      if (allPeriods) allPeriods.checked = true;
      if (recent) recent.checked = false;
      if (allGroups) allGroups.checked = true;
      const dimension = form.querySelector('select[name=dimension]');
      if (dimension) dimension.disabled = true;
    }
    form.requestSubmit();
  }
});
