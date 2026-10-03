/* =========================================================
   ShopGPT 2.0 — Main JavaScript
   Interactivity, animations, and utility functions
   ========================================================= */

'use strict';

// ─── Mobile Nav Toggle ────────────────────────────────────
(function initNav() {
  const toggle = document.querySelector('.nav-toggle');
  const links  = document.querySelector('.nav-links');
  if (!toggle || !links) return;

  toggle.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
    toggle.textContent = open ? '✕' : '☰';
  });

  // Close on outside click
  document.addEventListener('click', (e) => {
    if (!toggle.contains(e.target) && !links.contains(e.target)) {
      links.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
      toggle.textContent = '☰';
    }
  });
})();

// ─── Popular Search Chips → Fill Search Bar ───────────────
(function initPopularChips() {
  document.querySelectorAll('.popular-chip[data-query]').forEach(chip => {
    chip.addEventListener('click', (e) => {
      e.preventDefault();
      const q = chip.dataset.query;
      const input = document.querySelector('.search-bar-input, input[name="query"]');
      if (input) {
        input.value = q;
        input.focus();
        // Tiny shake-animation to show it was filled
        input.animate(
          [{ transform: 'scale(1)' }, { transform: 'scale(1.02)' }, { transform: 'scale(1)' }],
          { duration: 200 }
        );
      }
    });
  });
})();

// ─── Search Bar Loading State ─────────────────────────────
(function initSearchLoading() {
  const forms = document.querySelectorAll('form[data-search-form]');
  forms.forEach(form => {
    form.addEventListener('submit', (e) => {
      const input = form.querySelector('input[name="query"]');
      if (input && !input.value.trim()) {
        e.preventDefault();
        return;
      }

      const overlay = document.getElementById('loading-overlay');
      const mainContent = document.getElementById('home-main-content');
      if (overlay) overlay.classList.remove('hidden');
      if (mainContent) mainContent.classList.add('hidden');

      const btn = form.querySelector('[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner spinner-sm" style="display:inline-block"></span> Searching…';
      }
    });
  });
})();

// ─── Auto-refresh for pending searches ───────────────────
(function initAutoRefresh() {
  const flag = document.querySelector('[data-auto-refresh]');
  if (!flag) return;
  const delay = parseInt(flag.dataset.autoRefresh, 10) || 3000;
  setTimeout(() => window.location.reload(), delay);
})();

// ─── Toast Notification System ───────────────────────────
window.ShopGPT = window.ShopGPT || {};

window.ShopGPT.toast = function(message, type = 'info', duration = 4000) {
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
  const colors = {
    success: 'rgba(16,185,129,0.15)',
    error:   'rgba(239,68,68,0.15)',
    warning: 'rgba(245,158,11,0.15)',
    info:    'rgba(59,130,246,0.15)',
  };

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.style.borderLeft = `3px solid var(--${type === 'error' ? 'danger' : type === 'warning' ? 'warning' : type === 'success' ? 'success' : 'info'})`;
  toast.style.background = colors[type] || colors.info;
  toast.innerHTML = `<span>${icons[type] || '💬'}</span><span>${message}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'toast-in 0.3s ease reverse';
    setTimeout(() => toast.remove(), 300);
  }, duration);
};

// ─── Table Row Hover Highlight ───────────────────────────
(function initTableHover() {
  document.querySelectorAll('.compare-table tbody tr').forEach(row => {
    row.addEventListener('mouseenter', () => {
      row.style.background = 'rgba(124, 58, 237, 0.06)';
    });
    row.addEventListener('mouseleave', () => {
      row.style.background = '';
    });
  });
})();

// ─── Smooth Scroll for Anchor Links ──────────────────────
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', (e) => {
    const href = link.getAttribute('href');
    if (href === '#') return;
    try {
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (err) {
      console.warn('Invalid selector in anchor link:', href, err);
    }
  });
});

// ─── Card Hover Depth Effect ──────────────────────────────
(function initCardDepth() {
  document.querySelectorAll('.card-clickable, .product-card, .rec-card').forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * 8;
      card.style.transform = `translateY(-4px) rotateX(${-y}deg) rotateY(${x}deg)`;
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = '';
    });
  });
})();

// ─── Form Validation Feedback ─────────────────────────────
(function initFormValidation() {
  document.querySelectorAll('.form-control').forEach(input => {
    input.addEventListener('blur', () => {
      if (input.required && !input.value.trim()) {
        input.classList.add('is-invalid');
      } else {
        input.classList.remove('is-invalid');
      }
    });

    input.addEventListener('input', () => {
      if (input.value.trim()) {
        input.classList.remove('is-invalid');
      }
    });
  });
})();

// ─── Keyboard Shortcut: "/" focuses search ─────────────────
document.addEventListener('keydown', (e) => {
  if (e.key === '/' && !['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) {
    e.preventDefault();
    const input = document.querySelector('.search-bar-input, input[name="query"]');
    if (input) input.focus();
  }
});

// ─── Image Lazy Loading Fallback ──────────────────────────
document.querySelectorAll('img[data-src]').forEach(img => {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        img.src = img.dataset.src;
        observer.disconnect();
      }
    });
  });
  observer.observe(img);
});

// ─── Animate on Scroll (simple) ──────────────────────────
(function initScrollAnimate() {
  const els = document.querySelectorAll('.fade-in-scroll');
  if (!els.length) return;
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('fade-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  els.forEach(el => observer.observe(el));
})();

// ─── Copy to Clipboard Utility ────────────────────────────
window.ShopGPT.copy = function(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    const original = btn.textContent;
    btn.textContent = '✓ Copied!';
    setTimeout(() => { btn.textContent = original; }, 1500);
    window.ShopGPT.toast('Copied to clipboard', 'success', 2000);
  });
};

console.info('%cShopGPT 2.0 🛍️ — AI Shopping Assistant', 'color:#a855f7; font-weight:700; font-size:14px;');
