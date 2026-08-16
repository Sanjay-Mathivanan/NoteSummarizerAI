// Apply theme immediately on load to prevent flash of unstyled content (FOUC)
(function() {
  const currentTheme = localStorage.getItem('theme') || 'dark';
  if (currentTheme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();

document.addEventListener('DOMContentLoaded', () => {
  const themeToggle = document.getElementById('theme-toggle');
  if (!themeToggle) return;

  // Set initial icon matching the current theme state
  const currentTheme = localStorage.getItem('theme') || 'dark';
  themeToggle.innerHTML = currentTheme === 'light' ? '☀️' : '🌙';

  themeToggle.addEventListener('click', () => {
    let theme = 'dark';
    if (document.documentElement.getAttribute('data-theme') !== 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
      themeToggle.innerHTML = '☀️';
      theme = 'light';
    } else {
      document.documentElement.removeAttribute('data-theme');
      themeToggle.innerHTML = '🌙';
    }
    localStorage.setItem('theme', theme);
  });
});
