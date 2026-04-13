/**
 * 防災備蓄計算ツール - メインスクリプト
 * CALORIE_DATA / WATER_DATA / FOOD_ITEMS は index.php から渡される
 */

'use strict';

const STORAGE_KEY = 'ndma_stockpile_v1';

/* ===========================
   状態管理
   =========================== */
let members = [];          // [{ id, name, age, gender }]
let selectedDays = 1;      // 数値
let memberCounter = 0;
let selectedPresets = [];  // 選択中プリセットのid配列

/* ===========================
   初期化
   =========================== */
document.addEventListener('DOMContentLoaded', () => {
    initPeriodTabs();
    initSaveButtons();
    initPresetSelector();

    // 保存データがあれば自動読み込み
    const saved = loadFromStorage();
    if (saved) {
        members = saved.members || [];
        selectedDays = saved.selectedDays || 1;
        selectedPresets = saved.selectedPresets || [];
        memberCounter = members.length > 0
            ? Math.max(...members.map(m => m.id)) + 1
            : 0;
        renderAllCards();
        updateActivePeriodTab();
        updateResult();
        renderPresetSelector();
    } else {
        // 初期カードを1枚作る
        addMember();
    }

    document.getElementById('add-member-btn').addEventListener('click', addMember);
});

/* ===========================
   期間設定
   =========================== */
function initPeriodTabs() {
    const input = document.getElementById('period-input');

    // 数値直接入力
    input.addEventListener('input', () => {
        const val = parseInt(input.value, 10);
        if (!isNaN(val) && val >= 1) {
            selectedDays = val;
            updateActivePeriodTab();
            updateResult();
        }
    });

    // 範囲外入力を補正（blur時）
    input.addEventListener('blur', () => {
        if (input.value === '' || parseInt(input.value, 10) < 1) {
            input.value = 1;
            selectedDays = 1;
            updateActivePeriodTab();
            updateResult();
        }
    });

    // プリセットボタン
    document.querySelectorAll('.period-preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            selectedDays = parseInt(btn.dataset.days, 10);
            input.value = selectedDays;
            updateActivePeriodTab();
            updateResult();
        });
    });
}

function updateActivePeriodTab() {
    const input = document.getElementById('period-input');
    if (input) input.value = selectedDays;
    document.querySelectorAll('.period-preset-btn').forEach(btn => {
        btn.classList.toggle('active', parseInt(btn.dataset.days, 10) === selectedDays);
    });
}

/* ===========================
   メンバー管理
   =========================== */
function addMember() {
    const member = {
        id:     memberCounter++,
        name:   '',
        age:    '',
        gender: 'male',
    };
    members.push(member);
    renderAllCards();
    updateResult();
}

function removeMember(id) {
    members = members.filter(m => m.id !== id);
    renderAllCards();
    updateResult();
}

function updateMember(id, field, value) {
    const m = members.find(m => m.id === id);
    if (!m) return;
    m[field] = value;
    updateResult();
}

/* ===========================
   カードレンダリング
   =========================== */
function renderAllCards() {
    const container = document.getElementById('member-cards');
    container.innerHTML = '';

    if (members.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column:1/-1">
                <div class="empty-state-icon">👤</div>
                <p>「家族を追加する」ボタンから家族を追加してください</p>
            </div>`;
        return;
    }

    members.forEach((m, idx) => {
        const card = createMemberCard(m, idx + 1);
        container.appendChild(card);
    });
}

function createMemberCard(member, displayNum) {
    const card = document.createElement('div');
    card.className = 'member-card';
    card.dataset.id = member.id;

    card.innerHTML = `
        <div class="member-card-header">
            <span class="member-number">メンバー ${displayNum}</span>
            <button class="remove-btn" title="削除" aria-label="このメンバーを削除">✕</button>
        </div>
        <div class="form-row">
            <div class="form-group">
                <label class="form-label">呼び名（任意）</label>
                <input
                    type="text"
                    class="form-input"
                    placeholder="例: お父さん"
                    value="${escapeHtml(member.name)}"
                    data-field="name"
                    maxlength="20"
                >
            </div>
            <div class="form-group">
                <label class="form-label">年齢</label>
                <input
                    type="number"
                    class="form-input"
                    placeholder="例: 35"
                    value="${member.age !== '' ? member.age : ''}"
                    data-field="age"
                    min="1"
                    max="120"
                >
            </div>
            <div class="form-group">
                <label class="form-label">性別</label>
                <div class="gender-toggle">
                    <button
                        type="button"
                        class="gender-btn ${member.gender === 'male' ? 'active' : ''}"
                        data-gender="male"
                    >👦 男性</button>
                    <button
                        type="button"
                        class="gender-btn ${member.gender === 'female' ? 'active' : ''}"
                        data-gender="female"
                    >👧 女性</button>
                </div>
            </div>
        </div>
    `;

    // 削除ボタン
    card.querySelector('.remove-btn').addEventListener('click', () => {
        removeMember(member.id);
    });

    // テキスト入力
    card.querySelectorAll('.form-input').forEach(input => {
        input.addEventListener('input', () => {
            const field = input.dataset.field;
            const val = field === 'age' ? (input.value === '' ? '' : parseInt(input.value, 10)) : input.value;
            updateMember(member.id, field, val);
        });
    });

    // 性別ボタン
    card.querySelectorAll('.gender-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const gender = btn.dataset.gender;
            updateMember(member.id, 'gender', gender);
            card.querySelectorAll('.gender-btn').forEach(b => {
                b.classList.toggle('active', b.dataset.gender === gender);
            });
        });
    });

    return card;
}

/* ===========================
   カロリー・水計算
   =========================== */
function getCalorieForMember(member) {
    if (member.age === '' || member.age < 1) return null;
    const row = CALORIE_DATA.find(r => member.age >= r.min_age && member.age <= r.max_age);
    if (!row) return null;
    return member.gender === 'male' ? row.male : row.female;
}

function getWaterForMember(member) {
    if (member.age === '' || member.age < 1) return null;
    const row = WATER_DATA.find(r => member.age >= r.min_age && member.age <= r.max_age);
    if (!row) return null;
    return member.gender === 'male' ? row.male : row.female;
}

function getAgeLabel(age) {
    const row = CALORIE_DATA.find(r => age >= r.min_age && age <= r.max_age);
    return row ? row.label : '';
}

/* ===========================
   結果表示
   =========================== */
function updateResult() {
    const validMembers = members.filter(m => m.age !== '' && m.age >= 1);

    if (validMembers.length === 0) {
        document.getElementById('result-section').style.display = 'none';
        return;
    }

    document.getElementById('result-section').style.display = '';

    let totalCalorie = 0;
    let totalWater   = 0;

    const tbody = document.getElementById('member-detail-tbody');
    tbody.innerHTML = '';

    validMembers.forEach((m, idx) => {
        const kcal  = getCalorieForMember(m);
        const water = getWaterForMember(m);

        if (kcal === null || water === null) return;

        const totalKcal  = kcal  * selectedDays;
        const totalWaterM = water * selectedDays;

        totalCalorie += totalKcal;
        totalWater   += totalWaterM;

        const label  = m.name || `メンバー${idx + 1}`;
        const genderLabel = m.gender === 'male' ? '👦 男性' : '👧 女性';
        const ageLabel = getAgeLabel(m.age);

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${escapeHtml(label)}</td>
            <td>${m.age}歳 / ${ageLabel} / ${genderLabel}</td>
            <td class="calorie-value">${kcal.toLocaleString()} kcal</td>
            <td class="calorie-value">${totalKcal.toLocaleString()} kcal</td>
            <td class="water-value">${water.toLocaleString()} ml</td>
            <td class="water-value">${totalWaterM.toLocaleString()} ml</td>
        `;
        tbody.appendChild(tr);
    });

    document.getElementById('total-calorie').textContent = totalCalorie.toLocaleString();
    document.getElementById('total-water').textContent   = totalWater.toLocaleString();

    updateBottles(totalWater);
    updateFoodGrid();
}

/* ===========================
   ペットボトル換算
   =========================== */
function updateBottles(totalWaterMl) {
    document.getElementById('bottle-500').textContent  = Math.ceil(totalWaterMl / 500).toLocaleString();
    document.getElementById('bottle-1000').textContent = Math.ceil(totalWaterMl / 1000).toLocaleString();
    document.getElementById('bottle-2000').textContent = Math.ceil(totalWaterMl / 2000).toLocaleString();
}

/* ===========================
   プリセット選択
   =========================== */
const CATEGORY_LABELS = {
    staple:  '🍚 主食',
    side:    '🍛 おかず・副食',
    protein: '🥩 たんぱく質',
    soup:    '🍜 スープ・汁物',
    snack:   '🍫 間食・補助食品',
    drink:   '🥤 飲料',
};

function initPresetSelector() {
    renderPresetSelector();
}

function renderPresetSelector() {
    const container = document.getElementById('preset-selector');
    container.innerHTML = '';
    FOOD_PRESETS.forEach(preset => {
        const isSelected = selectedPresets.includes(preset.id);
        const card = document.createElement('div');
        card.className = 'preset-card' + (isSelected ? ' selected' : '');
        card.dataset.presetId = preset.id;

        // 食品名タグのプレビュー（最大4件）
        const previewTags = preset.items.slice(0, 4).map(item => {
            const food = FOOD_ITEMS.find(f => f.id === item.food_id);
            return food ? `<span class="preset-item-tag">${escapeHtml(food.name)}</span>` : '';
        }).join('');
        const moreCount = preset.items.length > 4 ? `<span class="preset-item-tag">+${preset.items.length - 4}</span>` : '';

        card.innerHTML = `
            <div class="preset-card-header">
                <span class="preset-icon">${preset.icon}</span>
                <span class="preset-name">${escapeHtml(preset.name)}</span>
                <span class="preset-check"></span>
            </div>
            <div class="preset-desc">${escapeHtml(preset.description)}</div>
            <div class="preset-items-preview">${previewTags}${moreCount}</div>
        `;
        card.addEventListener('click', () => togglePreset(preset.id));
        container.appendChild(card);
    });
}

function togglePreset(presetId) {
    if (selectedPresets.includes(presetId)) {
        selectedPresets = selectedPresets.filter(id => id !== presetId);
    } else {
        selectedPresets.push(presetId);
    }
    renderPresetSelector();
    updateSelectedPresetsBar();
    updateFoodGrid();
}

function updateSelectedPresetsBar() {
    const bar  = document.getElementById('selected-presets-bar');
    const tags = document.getElementById('selected-preset-tags');
    if (selectedPresets.length === 0) {
        bar.style.display = 'none';
        return;
    }
    bar.style.display = '';
    tags.innerHTML = selectedPresets.map(id => {
        const p = FOOD_PRESETS.find(p => p.id === id);
        return p ? `<span class="selected-tag">${p.icon} ${escapeHtml(p.name)}</span>` : '';
    }).join('');
}

/* ===========================
   防災食品グリッド（プリセット計算）
   =========================== */
function updateFoodGrid() {
    const grid       = document.getElementById('food-grid');
    const resultArea = document.getElementById('food-result-area');
    const emptyState = document.getElementById('food-empty-state');

    if (selectedPresets.length === 0) {
        resultArea.style.display = 'none';
        emptyState.style.display = '';
        return;
    }
    resultArea.style.display = '';
    emptyState.style.display = 'none';

    // 合計カロリーを取得
    const validMembers = members.filter(m => m.age !== '' && m.age >= 1);
    let totalCalorie = 0;
    validMembers.forEach(m => {
        const kcal = getCalorieForMember(m);
        if (kcal !== null) totalCalorie += kcal * selectedDays;
    });

    // 選択プリセットを等分配分で合成（各プリセットのratio合計を正規化）
    // food_id ごとに「割り当てカロリー」を集計
    const allocMap = {}; // food_id => 割り当て総カロリー
    const share = 1 / selectedPresets.length; // 各プリセットへの配分比率（均等）

    selectedPresets.forEach(presetId => {
        const preset = FOOD_PRESETS.find(p => p.id === presetId);
        if (!preset) return;
        preset.items.forEach(item => {
            const alloc = totalCalorie * share * item.ratio;
            allocMap[item.food_id] = (allocMap[item.food_id] || 0) + alloc;
        });
    });

    // food_id を category でグループ化して表示
    const byCategory = {};
    Object.entries(allocMap).forEach(([foodId, allocKcal]) => {
        const food = FOOD_ITEMS.find(f => f.id === foodId);
        if (!food) return;
        if (!byCategory[food.category]) byCategory[food.category] = [];
        byCategory[food.category].push({ food, allocKcal });
    });

    grid.innerHTML = '';

    const categoryOrder = ['staple', 'side', 'protein', 'soup', 'snack', 'drink'];
    categoryOrder.forEach(cat => {
        if (!byCategory[cat]) return;
        const titleEl = document.createElement('div');
        titleEl.className = 'food-category-title';
        titleEl.textContent = CATEGORY_LABELS[cat] || cat;
        grid.appendChild(titleEl);

        byCategory[cat].forEach(({ food, allocKcal }) => {
            const count = Math.ceil(allocKcal / food.kcal);
            const card = document.createElement('div');
            card.className = 'food-card';
            card.innerHTML = `
                <div class="food-card-name">${escapeHtml(food.name)}</div>
                <div class="food-card-kcal">1${escapeHtml(food.unit)} = ${food.kcal.toLocaleString()} kcal</div>
                <div class="food-card-count">${count.toLocaleString()}</div>
                <div class="food-card-count-unit">${escapeHtml(food.unit.replace(/（.*）/, ''))}</div>
                <div class="food-card-note">${escapeHtml(food.note)}</div>
            `;
            grid.appendChild(card);
        });
    });
}

/* ===========================
   保存・読み込み
   =========================== */
function initSaveButtons() {
    document.getElementById('save-btn').addEventListener('click', saveToStorage);
    document.getElementById('load-btn').addEventListener('click', () => {
        const saved = loadFromStorage();
        if (saved) {
            members = saved.members || [];
            selectedDays = saved.selectedDays || 1;
            memberCounter = members.length > 0
                ? Math.max(...members.map(m => m.id)) + 1
                : 0;
            selectedPresets = saved.selectedPresets || [];
            renderAllCards();
            updateActivePeriodTab();
            updateResult();
            renderPresetSelector();
            updateSelectedPresetsBar();
            updateFoodGrid();
            showStatus('保存データを読み込みました。', 'success');
        } else {
            showStatus('保存されたデータがありません。', 'error');
        }
    });
    document.getElementById('clear-btn').addEventListener('click', () => {
        if (!confirm('ブラウザに保存されたデータを削除しますか？')) return;
        try {
            localStorage.removeItem(STORAGE_KEY);
            showStatus('保存データを削除しました。', 'info');
        } catch (e) {
            showStatus('削除に失敗しました。', 'error');
        }
    });
}

function saveToStorage() {
    try {
        const data = {
            members,
            selectedDays,
            selectedPresets,
            savedAt: new Date().toLocaleString('ja-JP'),
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        showStatus(`データを保存しました（${data.savedAt}）`, 'success');
    } catch (e) {
        showStatus('保存に失敗しました。ブラウザの設定を確認してください。', 'error');
    }
}

function loadFromStorage() {
    try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        return JSON.parse(raw);
    } catch (e) {
        return null;
    }
}

function showStatus(msg, type) {
    const el = document.getElementById('save-status');
    el.textContent = msg;
    el.className = `save-status ${type}`;
    clearTimeout(el._timer);
    el._timer = setTimeout(() => {
        el.className = 'save-status';
    }, 5000);
}

/* ===========================
   ユーティリティ
   =========================== */
function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
