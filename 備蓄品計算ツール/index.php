<?php
require_once __DIR__ . '/data.php';
?>
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>防災備蓄計算ツール</title>
    <link rel="stylesheet" href="style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
</head>
<body>

<header class="site-header">
    <div class="container">
        <div class="header-inner">
            <div class="header-icon">🏠</div>
            <div>
                <h1 class="site-title">防災備蓄計算ツール</h1>
                <p class="site-subtitle">家族構成を入力して、必要な備蓄量を計算しましょう</p>
            </div>
        </div>
    </div>
</header>

<main class="main-content">
    <div class="container">

        <!-- 家族メンバー入力セクション -->
        <section class="section" id="member-section">
            <div class="section-header">
                <h2 class="section-title">👨‍👩‍👧‍👦 家族構成の入力</h2>
                <p class="section-desc">家族一人ひとりの年齢と性別を入力してください。</p>
            </div>

            <div id="member-cards" class="member-cards">
                <!-- カードはJavaScriptで生成 -->
            </div>

            <div class="add-member-area">
                <button id="add-member-btn" class="btn btn-add">
                    <span class="btn-icon">＋</span> 家族を追加する
                </button>
            </div>
        </section>

        <!-- 備蓄期間選択 -->
        <section class="section" id="period-section">
            <div class="section-header">
                <h2 class="section-title">📅 備蓄期間の設定</h2>
            </div>
            <div class="period-input-row">
                <div class="period-presets">
                    <button class="period-preset-btn" data-days="1">1日</button>
                    <button class="period-preset-btn" data-days="3">3日</button>
                    <button class="period-preset-btn" data-days="7">7日</button>
                    <button class="period-preset-btn" data-days="14">2週間</button>
                    <button class="period-preset-btn" data-days="30">1ヶ月</button>
                </div>
                <div class="period-custom">
                    <input
                        type="number"
                        id="period-input"
                        class="period-number-input"
                        value="1"
                        min="1"
                        max="365"
                        aria-label="備蓄日数"
                    >
                    <span class="period-unit">日分</span>
                </div>
            </div>
        </section>

        <!-- 計算結果セクション -->
        <section class="section" id="result-section" style="display:none;">
            <div class="section-header">
                <h2 class="section-title">📊 必要な備蓄量</h2>
            </div>

            <!-- サマリーカード -->
            <div class="result-summary">
                <div class="summary-card card-calorie">
                    <div class="summary-icon">🔥</div>
                    <div class="summary-label">合計必要カロリー</div>
                    <div class="summary-value" id="total-calorie">0</div>
                    <div class="summary-unit">kcal</div>
                </div>
                <div class="summary-card card-water">
                    <div class="summary-icon">💧</div>
                    <div class="summary-label">合計必要水分量</div>
                    <div class="summary-value" id="total-water">0</div>
                    <div class="summary-unit">ml</div>
                </div>
            </div>

            <!-- 内訳テーブル -->
            <div class="result-detail">
                <h3 class="detail-title">👤 メンバー別内訳</h3>
                <div class="table-wrapper">
                    <table class="result-table" id="member-detail-table">
                        <thead>
                            <tr>
                                <th>メンバー</th>
                                <th>年齢・性別</th>
                                <th>1日カロリー</th>
                                <th>合計カロリー</th>
                                <th>1日水分量</th>
                                <th>合計水分量</th>
                            </tr>
                        </thead>
                        <tbody id="member-detail-tbody">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 水ペットボトル換算 -->
            <div class="result-detail">
                <h3 class="detail-title">🍶 必要なペットボトル本数</h3>
                <div class="bottle-grid" id="bottle-grid">
                    <div class="bottle-card">
                        <div class="bottle-icon">🧴</div>
                        <div class="bottle-size">500ml</div>
                        <div class="bottle-count"><span id="bottle-500">0</span> 本</div>
                    </div>
                    <div class="bottle-card">
                        <div class="bottle-icon">🧴</div>
                        <div class="bottle-size">1,000ml（1L）</div>
                        <div class="bottle-count"><span id="bottle-1000">0</span> 本</div>
                    </div>
                    <div class="bottle-card">
                        <div class="bottle-icon">🧴</div>
                        <div class="bottle-size">2,000ml（2L）</div>
                        <div class="bottle-count"><span id="bottle-2000">0</span> 本</div>
                    </div>
                </div>
                <p class="bottle-note">※ 水分量は飲料水＋調理用水の合計です（内閣府防災指針：1人1日最低3L目安）</p>
            </div>

            <!-- 防災食品換算 -->
            <div class="result-detail" id="food-preset-section">
                <h3 class="detail-title">🥫 防災食品の必要数（プリセット組み合わせ）</h3>
                <p class="food-note">プリセットを選択すると、その概算に必要な食品または架空の組み合わせによる必要数を表示します。<br>複数プリセットを選択すると比率を按分して計算します。</p>
                <!-- プリセット選択 -->
                <div id="preset-selector" class="preset-selector">
                    <!-- JavaScriptで生成 -->
                </div>
                <!-- 選択中プリセット表示 -->
                <div id="selected-presets-bar" class="selected-presets-bar" style="display:none;">
                    <span class="selected-label">選択中:</span>
                    <div id="selected-preset-tags" class="selected-preset-tags"></div>
                </div>
                <!-- 結果グリッド -->
                <div id="food-result-area" class="food-result-area" style="display:none;">
                    <div id="food-grid" class="food-grid">
                        <!-- JavaScriptで生成 -->
                    </div>
                </div>
                <div id="food-empty-state" class="food-empty-placeholder">
                    <div class="empty-state-icon">💆</div>
                    <p>上のプリセットから食事の種類を選んでください</p>
                </div>
            </div>
        </section>

        <!-- データ保存セクション -->
        <section class="section" id="save-section">
            <div class="section-header">
                <h2 class="section-title">💾 データの保存・読み込み</h2>
                <p class="section-desc">入力したデータをブラウザに保存できます。次回アクセス時に自動で読み込まれます。</p>
            </div>
            <div class="save-buttons">
                <button id="save-btn" class="btn btn-save">💾 ブラウザに保存</button>
                <button id="load-btn" class="btn btn-load">📂 保存データを読み込む</button>
                <button id="clear-btn" class="btn btn-clear">🗑 保存データを削除</button>
            </div>
            <div id="save-status" class="save-status"></div>
        </section>

        <!-- 参考情報 -->
        <section class="section" id="reference-section">
            <div class="section-header">
                <h2 class="section-title">📚 参考情報・出典</h2>
            </div>
            <div class="reference-list">
                <div class="reference-item">
                    <span class="ref-icon">🏛</span>
                    <div>
                        <strong>厚生労働省</strong>「日本人の食事摂取基準（2020年版）」<br>
                        <small>各年齢・性別の推定エネルギー必要量・水分必要量の基礎データとして使用</small>
                    </div>
                </div>
                <div class="reference-item">
                    <span class="ref-icon">🏛</span>
                    <div>
                        <strong>内閣府防災</strong>「家庭での備蓄の仕方」<br>
                        <small>備蓄量の目安（1人1日3L）として参照</small>
                    </div>
                </div>
                <div class="reference-item">
                    <span class="ref-icon">🌾</span>
                    <div>
                        <strong>農林水産省</strong>「災害時に備えた食品ストックガイド」<br>
                        <small>推奨備蓄食品リストおよびカロリー情報として参照</small>
                    </div>
                </div>
                <div class="reference-item">
                    <span class="ref-icon">🗼</span>
                    <div>
                        <strong>東京都防災</strong>「東京備蓄ナビ」<br>
                        <small>食品カロリー・水量計算の参考として使用</small>
                    </div>
                </div>
                <div class="reference-item">
                    <span class="ref-icon">🥗</span>
                    <div>
                        <strong>日本栄養士会</strong>「災害時の食事支援」<br>
                        <small>年代別・状況別の栄養指針として参照</small>
                    </div>
                </div>
            </div>
        </section>

    </div><!-- /.container -->
</main>

<footer class="site-footer">
    <div class="container">
        <p>© 防災備蓄計算ツール｜データ出典: 厚生労働省・内閣府防災・農林水産省・東京都防災・日本栄養士会</p>
    </div>
</footer>

<!-- マスターデータをJavaScriptへ渡す -->
<script>
const CALORIE_DATA  = <?= $jsonCalorieData ?>;
const WATER_DATA    = <?= $jsonWaterData ?>;
const FOOD_ITEMS    = <?= $jsonFoodItems ?>;
const FOOD_PRESETS  = <?= $jsonFoodPresets ?>;
</script>
<script src="app.js"></script>

</body>
</html>
