/**
 * View Rendering Service
 * Handles DOM updates, table rendering, badges, KPIs, and sanitization.
 */

import { CONFIG } from './config.js';

export class RenderService {
  /**
   * Updates all top KPI cards.
   */
  updateKPIs({ problems, progress, solvedIds, bookmarkedIds }) {
    const totalSent = problems.length;

    // 1. Streak
    const streak = progress?.streak_days ?? this._calcStreak(problems);
    const streakElem = document.getElementById('statStreak');
    if (streakElem) streakElem.textContent = String(streak);

    // 2. Total Sent
    const totalElem = document.getElementById('statTotalSent');
    if (totalElem) totalElem.textContent = String(totalSent);

    // 3. User Solved Metrics
    const solvedCount = problems.filter((p) => solvedIds.has(p.id)).length;
    const solvedPercent = totalSent > 0 ? Math.round((solvedCount / totalSent) * 100) : 0;

    const solvedUserElem = document.getElementById('statSolvedUser');
    if (solvedUserElem) solvedUserElem.textContent = String(solvedCount);

    const solvedCountElem = document.getElementById('statSolvedCount');
    if (solvedCountElem) {
      solvedCountElem.textContent = `${solvedCount} marked solved (${solvedPercent}%)`;
    }

    // 4. Bookmarks
    const bookmarkedCount = problems.filter((p) => bookmarkedIds.has(p.id)).length;
    const bmElem = document.getElementById('statBookmarkedCount');
    if (bmElem) bmElem.textContent = `${bookmarkedCount} bookmarked for revision`;

    // 5. Striver A2Z Sheet Progress
    const a2zSent = problems.filter(
      (p) => p.source === 'a2z_sheet' || p.id.startsWith('a2z-')
    ).length;
    const a2zTotal = progress?.a2z_total || 455;
    const a2zPercent = Math.min(100, Math.round((a2zSent / a2zTotal) * 100));

    const a2zPercentElem = document.getElementById('statA2ZPercent');
    if (a2zPercentElem) a2zPercentElem.textContent = `${a2zPercent}%`;

    const a2zRatioElem = document.getElementById('statA2ZRatio');
    if (a2zRatioElem) a2zRatioElem.textContent = `(${a2zSent} / ${a2zTotal})`;

    const a2zBar = document.getElementById('statA2ZBar');
    if (a2zBar) a2zBar.style.width = `${a2zPercent}%`;
  }

  /**
   * Renders rows in the problem table.
   */
  renderTable(problems, { solvedIds, bookmarkedIds }) {
    const tbody = document.getElementById('problemsTableBody');
    const emptyState = document.getElementById('tableEmptyState');
    if (!tbody) return;

    if (!problems.length) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.classList.remove('hidden');
      return;
    }

    if (emptyState) emptyState.classList.add('hidden');

    tbody.innerHTML = problems
      .map((p) => {
        const isSolved = solvedIds.has(p.id);
        const isBookmarked = bookmarkedIds.has(p.id);
        const diffBadge = this.getDifficultyBadge(p.difficulty);
        const sourceBadge = this.getSourceBadge(p.source);
        const dateFormatted = this.formatDate(p.date);

        return `
        <tr class="hover:bg-gray-800/40 transition group ${isSolved ? 'opacity-70 bg-gray-900/30' : ''}" data-problem-id="${this.escape(p.id)}">
          <!-- Checkbox -->
          <td class="py-3 px-4 text-center">
            <input 
              type="checkbox" 
              data-action="solve"
              data-id="${this.escape(p.id)}" 
              class="w-4 h-4 rounded border-gray-700 bg-gray-800 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              ${isSolved ? 'checked' : ''}
              title="${isSolved ? 'Mark as unsolved' : 'Mark as solved'}"
            />
          </td>

          <!-- Bookmark Star -->
          <td class="py-3 px-2 text-center">
            <button 
              data-action="bookmark"
              data-id="${this.escape(p.id)}" 
              class="p-1 hover:scale-110 transition ${isBookmarked ? 'text-amber-400' : 'text-gray-600 hover:text-gray-400'}"
              title="${isBookmarked ? 'Remove bookmark' : 'Bookmark for revision'}"
            >
              <i data-lucide="star" class="w-4 h-4 ${isBookmarked ? 'fill-amber-400' : ''}"></i>
            </button>
          </td>

          <!-- Date -->
          <td class="py-3 px-4 font-mono text-xs text-gray-400 whitespace-nowrap">
            ${dateFormatted}
          </td>

          <!-- Problem Title & Link -->
          <td class="py-3 px-4">
            <div class="flex items-center gap-2">
              <a 
                href="${this.escape(p.url)}" 
                target="_blank" 
                rel="noopener noreferrer" 
                class="font-medium text-gray-200 hover:text-indigo-400 transition flex items-center gap-1.5 group-hover:translate-x-0.5 transform duration-150 ${isSolved ? 'line-through text-gray-400' : ''}"
              >
                <span>${this.escape(p.title)}</span>
                <i data-lucide="external-link" class="w-3.5 h-3.5 text-gray-500 group-hover:text-indigo-400 transition shrink-0"></i>
              </a>
            </div>
            ${p.id ? `<span class="text-[10px] font-mono text-gray-500">${this.escape(p.id)}</span>` : ''}
          </td>

          <!-- Difficulty Badge -->
          <td class="py-3 px-4">
            ${diffBadge}
          </td>

          <!-- Topic Badge -->
          <td class="py-3 px-4 text-xs font-medium text-gray-300">
            <span class="inline-block px-2.5 py-1 rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              ${this.escape(p.topic || 'General')}
            </span>
          </td>

          <!-- Source Badge -->
          <td class="py-3 px-4">
            ${sourceBadge}
          </td>
        </tr>
      `;
      })
      .join('');

    // Re-render Lucide icons for injected rows
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  /**
   * Returns HTML for difficulty badge.
   */
  getDifficultyBadge(diff) {
    const theme = CONFIG.themes.difficulties[diff] || CONFIG.themes.difficulties.Medium;
    return `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${theme.bg} ${theme.text} ${theme.border}">${this.escape(diff)}</span>`;
  }

  /**
   * Returns HTML for source badge.
   */
  getSourceBadge(src) {
    const key = String(src || '').toLowerCase();
    let theme = CONFIG.themes.sources[key];
    let label = src;

    if (!theme) {
      if (key.includes('a2z')) theme = CONFIG.themes.sources.a2z_sheet;
      else if (key.includes('leet')) theme = CONFIG.themes.sources.leetcode;
      else if (key.includes('gfg')) theme = CONFIG.themes.sources.gfg;
      else if (key.includes('codeforces')) theme = CONFIG.themes.sources.codeforces;
    }

    const color = theme ? theme.color : 'bg-gray-800 text-gray-300 border-gray-700';
    label = theme ? theme.label : src.toUpperCase();

    return `<span class="inline-block px-2 py-0.5 rounded text-[11px] font-mono border ${color}">${this.escape(label)}</span>`;
  }

  /**
   * Updates pagination indicators.
   */
  updatePagination(totalItems, currentPage, pageSize) {
    const size = pageSize === 'ALL' ? totalItems : pageSize;
    const totalPages = Math.max(1, Math.ceil(totalItems / (size || 1)));

    const pageInfo = document.getElementById('pageInfoText');
    const btnPrev = document.getElementById('btnPrevPage');
    const btnNext = document.getElementById('btnNextPage');

    if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;
    if (btnPrev) btnPrev.disabled = currentPage <= 1;
    if (btnNext) btnNext.disabled = currentPage >= totalPages;
  }

  /**
   * Renders source distribution chips.
   */
  renderSourceChips(container, sourceCounts) {
    if (!container) return;
    const chipsHtml = Object.entries(sourceCounts)
      .map(([src, count]) => {
        const theme = CONFIG.themes.sources[src] || { label: src.toUpperCase() };
        return `
        <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300 font-mono text-[11px] border border-gray-700">
          <span class="w-1.5 h-1.5 rounded-full bg-indigo-400"></span>
          <span>${this.escape(theme.label)}</span>
          <span class="text-indigo-400 font-semibold">${count}</span>
        </span>
      `;
      })
      .join('');

    container.innerHTML = `<span class="text-gray-500 font-medium mr-1">Sources:</span>${chipsHtml}`;
  }

  /**
   * Populates topic dropdown filter options.
   */
  populateTopicFilter(select, topics, currentSelected) {
    if (!select) return;
    select.innerHTML = '<option value="ALL">All Topics</option>';
    for (const t of topics) {
      const opt = document.createElement('option');
      opt.value = t;
      opt.textContent = t;
      if (t === currentSelected) opt.selected = true;
      select.appendChild(opt);
    }
  }

  /**
   * Updates the navbar connection status pill.
   */
  updateConnectionStatus(status, label) {
    const container = document.getElementById('connectionStatus');
    const textElem = document.getElementById('statusText');
    const dot = document.getElementById('statusDot');
    const pulse = document.getElementById('statusPulse');

    if (!container || !textElem || !dot || !pulse) return;
    textElem.textContent = label;

    if (status === 'live') {
      dot.className = 'relative inline-flex rounded-full h-2 w-2 bg-emerald-500';
      pulse.className = 'animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75';
      container.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-950/40 border border-emerald-800/60 text-xs text-emerald-300 font-medium';
    } else if (status === 'loading') {
      dot.className = 'relative inline-flex rounded-full h-2 w-2 bg-indigo-500';
      pulse.className = 'animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75';
      container.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-950/40 border border-indigo-800/60 text-xs text-indigo-300 font-medium';
    } else {
      // Local fallback or offline
      dot.className = 'relative inline-flex rounded-full h-2 w-2 bg-gray-400';
      pulse.className = 'hidden';
      container.className = 'flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-800/80 border border-gray-700/60 text-xs text-gray-300 font-medium';
    }
  }

  /**
   * Toggles table skeleton loading state.
   */
  toggleLoading(isLoading) {
    const loader = document.getElementById('tableLoadingState');
    const tbody = document.getElementById('problemsTableBody');
    if (loader) {
      if (isLoading) {
        loader.classList.remove('hidden');
        if (tbody) tbody.innerHTML = '';
      } else {
        loader.classList.add('hidden');
      }
    }
  }

  formatDate(dateStr) {
    if (!dateStr) return '—';
    try {
      const parts = String(dateStr).split('T')[0].split('-');
      if (parts.length === 3) {
        const d = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      }
      return dateStr;
    } catch {
      return dateStr;
    }
  }

  escape(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  _calcStreak(problems) {
    if (!problems.length) return 0;
    const dates = new Set(problems.map((p) => p.date).filter(Boolean));
    let streak = 0;
    const cur = new Date();
    while (true) {
      const iso = cur.toISOString().split('T')[0];
      if (dates.has(iso)) {
        streak++;
        cur.setDate(cur.getDate() - 1);
      } else {
        break;
      }
    }
    return streak;
  }
}

export const renderService = new RenderService();
