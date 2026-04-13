<?php
/**
 * 防災備蓄計算ツール - マスターデータ
 *
 * 参考資料:
 * - 厚生労働省「日本人の食事摂取基準（2020年版）」
 * - 内閣府防災「家庭での備蓄の仕方」
 * - 農林水産省「災害時に備えた食品ストックガイド」
 * - 東京都防災「東京備蓄ナビ」
 * - 日本栄養士会「災害時の食事支援」
 */

/**
 * 年齢・性別ごとの1日必要カロリー（kcal）
 * 出典: 厚生労働省「日本人の食事摂取基準（2020年版）」推定エネルギー必要量
 * 身体活動レベルII（ふつう）を基準に、
 * 災害時は活動が限られるため身体活動レベルI（低い）を採用
 */
$calorieData = [
    // [ label, min_age, max_age, male_kcal, female_kcal ]
    ['label' => '1〜2歳',   'min_age' => 1,  'max_age' => 2,  'male' => 950,  'female' => 900],
    ['label' => '3〜5歳',   'min_age' => 3,  'max_age' => 5,  'male' => 1300, 'female' => 1250],
    ['label' => '6〜7歳',   'min_age' => 6,  'max_age' => 7,  'male' => 1550, 'female' => 1450],
    ['label' => '8〜9歳',   'min_age' => 8,  'max_age' => 9,  'male' => 1850, 'female' => 1700],
    ['label' => '10〜11歳', 'min_age' => 10, 'max_age' => 11, 'male' => 2250, 'female' => 2100],
    ['label' => '12〜14歳', 'min_age' => 12, 'max_age' => 14, 'male' => 2600, 'female' => 2400],
    ['label' => '15〜17歳', 'min_age' => 15, 'max_age' => 17, 'male' => 2800, 'female' => 2300],
    ['label' => '18〜29歳', 'min_age' => 18, 'max_age' => 29, 'male' => 2300, 'female' => 1700],
    ['label' => '30〜49歳', 'min_age' => 30, 'max_age' => 49, 'male' => 2300, 'female' => 1750],
    ['label' => '50〜64歳', 'min_age' => 50, 'max_age' => 64, 'male' => 2200, 'female' => 1650],
    ['label' => '65〜74歳', 'min_age' => 65, 'max_age' => 74, 'male' => 2050, 'female' => 1550],
    ['label' => '75歳以上', 'min_age' => 75, 'max_age' => 120, 'male' => 1800, 'female' => 1400],
];

/**
 * 1日に必要な水の量（ml）
 * 出典:
 * - 内閣府防災「家庭での備蓄」：1人1日3L（飲料水+調理用）
 * - 農林水産省「災害時に備えた食品ストックガイド」：1人1日3L
 * - 環境省「熱中症環境保健マニュアル」：飲料水として1.2L/日
 * 年代別は厚生労働省「日本人の食事摂取基準」水分必要量を参考
 */
$waterData = [
    // [ label, min_age, max_age, male_ml, female_ml ]
    ['label' => '1〜2歳',   'min_age' => 1,  'max_age' => 2,  'male' => 1300, 'female' => 1300],
    ['label' => '3〜5歳',   'min_age' => 3,  'max_age' => 5,  'male' => 1600, 'female' => 1600],
    ['label' => '6〜7歳',   'min_age' => 6,  'max_age' => 7,  'male' => 1800, 'female' => 1800],
    ['label' => '8〜9歳',   'min_age' => 8,  'max_age' => 9,  'male' => 2000, 'female' => 2000],
    ['label' => '10〜11歳', 'min_age' => 10, 'max_age' => 11, 'male' => 2200, 'female' => 2200],
    ['label' => '12〜14歳', 'min_age' => 12, 'max_age' => 14, 'male' => 2600, 'female' => 2400],
    ['label' => '15〜17歳', 'min_age' => 15, 'max_age' => 17, 'male' => 3000, 'female' => 2500],
    ['label' => '18〜29歳', 'min_age' => 18, 'max_age' => 29, 'male' => 3000, 'female' => 2500],
    ['label' => '30〜49歳', 'min_age' => 30, 'max_age' => 49, 'male' => 3000, 'female' => 2500],
    ['label' => '50〜64歳', 'min_age' => 50, 'max_age' => 64, 'male' => 2800, 'female' => 2400],
    ['label' => '65〜74歳', 'min_age' => 65, 'max_age' => 74, 'male' => 2600, 'female' => 2200],
    ['label' => '75歳以上', 'min_age' => 75, 'max_age' => 120, 'male' => 2500, 'female' => 2100],
];

/**
 * 代表的な防災食品のカロリー
 * 出典: 各メーカー公表値・農林水産省「災害時に備えた食品ストックガイド」
 * 一般的な市販品の平均値を使用
 */
$foodItems = [
    // ── 主食 ──
    [
        'id'       => 'alpha_rice_white',
        'name'     => 'アルファ米（白米）',
        'kcal'     => 356,
        'unit'     => '食（100g）',
        'note'     => 'お湯または水で戻すだけ。5〜7年保存可能',
        'category' => 'staple',
    ],
    [
        'id'       => 'alpha_rice_mixed',
        'name'     => 'アルファ米（五目ごはん）',
        'kcal'     => 352,
        'unit'     => '食（100g）',
        'note'     => '具材入りで栄養バランスが良い',
        'category' => 'staple',
    ],
    [
        'id'       => 'alpha_rice_takikomi',
        'name'     => 'アルファ米（炊き込みごはん）',
        'kcal'     => 348,
        'unit'     => '食（100g）',
        'note'     => '具材の旨味で食欲増進。気分転換にも',
        'category' => 'staple',
    ],
    [
        'id'       => 'retort_rice_pack',
        'name'     => 'レトルトパックご飯',
        'kcal'     => 297,
        'unit'     => '食（200g）',
        'note'     => '電子レンジまたは湯煎。水不要で調理可',
        'category' => 'staple',
    ],
    [
        'id'       => 'crackers',
        'name'     => '乾パン・ビスケット',
        'kcal'     => 440,
        'unit'     => '袋（100g）',
        'note'     => 'エネルギー密度が高く保存に適している',
        'category' => 'staple',
    ],
    [
        'id'       => 'bread_can',
        'name'     => 'パン（缶詰）',
        'kcal'     => 285,
        'unit'     => '缶（100g）',
        'note'     => '5年保存可能。甘い系・プレーン系あり',
        'category' => 'staple',
    ],
    [
        'id'       => 'instant_noodle',
        'name'     => 'インスタントラーメン（袋）',
        'kcal'     => 380,
        'unit'     => '食（85g）',
        'note'     => '調理に水が必要。カップ麺より水節約可能',
        'category' => 'staple',
    ],
    [
        'id'       => 'cup_noodle',
        'name'     => 'カップ麺',
        'kcal'     => 340,
        'unit'     => '個（77g）',
        'note'     => 'お湯を注ぐだけ。手軽に食べられる',
        'category' => 'staple',
    ],
    [
        'id'       => 'cup_udon',
        'name'     => 'カップうどん',
        'kcal'     => 280,
        'unit'     => '個（72g）',
        'note'     => '塩分控えめ商品もあり。消化が良い',
        'category' => 'staple',
    ],
    [
        'id'       => 'pasta_dry',
        'name'     => 'パスタ（乾麺）',
        'kcal'     => 375,
        'unit'     => '食（100g）',
        'note'     => '長期保存可能。レトルトソースと組み合わせ',
        'category' => 'staple',
    ],
    [
        'id'       => 'retort_rice_porridge',
        'name'     => 'レトルトおかゆ',
        'kcal'     => 71,
        'unit'     => '袋（250g）',
        'note'     => '高齢者・乳幼児・体調不良時に適している',
        'category' => 'staple',
    ],
    // ── おかず・副食 ──
    [
        'id'       => 'retort_curry',
        'name'     => 'レトルトカレー',
        'kcal'     => 180,
        'unit'     => '袋（200g）',
        'note'     => '温めずにそのまま食べられる商品もあり',
        'category' => 'side',
    ],
    [
        'id'       => 'retort_pasta_sauce',
        'name'     => 'レトルトパスタソース',
        'kcal'     => 130,
        'unit'     => '袋（140g）',
        'note'     => 'ミートソース・ナポリタン等。パスタと組み合わせ',
        'category' => 'side',
    ],
    [
        'id'       => 'retort_stew',
        'name'     => 'レトルトシチュー',
        'kcal'     => 195,
        'unit'     => '袋（200g）',
        'note'     => '野菜・肉類を補える。パンとの相性も良い',
        'category' => 'side',
    ],
    [
        'id'       => 'retort_rice_bowl',
        'name'     => 'レトルト丼の素（牛丼・親子丼等）',
        'kcal'     => 160,
        'unit'     => '袋（150g）',
        'note'     => 'ご飯にかけるだけ。食欲増進に効果的',
        'category' => 'side',
    ],
    // ── たんぱく質 ──
    [
        'id'       => 'canned_sardine',
        'name'     => '缶詰（いわし）',
        'kcal'     => 190,
        'unit'     => '缶（100g）',
        'note'     => 'たんぱく質・DHA豊富。プルトップ型推奨',
        'category' => 'protein',
    ],
    [
        'id'       => 'canned_tuna',
        'name'     => '缶詰（ツナ）',
        'kcal'     => 267,
        'unit'     => '缶（140g）',
        'note'     => '高たんぱく・保存期間3年以上',
        'category' => 'protein',
    ],
    [
        'id'       => 'canned_mackerel',
        'name'     => '缶詰（さば水煮）',
        'kcal'     => 174,
        'unit'     => '缶（190g）',
        'note'     => 'EPA・DHAが豊富。生活習慣病予防にも',
        'category' => 'protein',
    ],
    [
        'id'       => 'canned_chicken',
        'name'     => '缶詰（鶏肉・焼き鳥）',
        'kcal'     => 170,
        'unit'     => '缶（85g）',
        'note'     => 'そのまま食べられる。子どもにも人気',
        'category' => 'protein',
    ],
    [
        'id'       => 'canned_beef',
        'name'     => '缶詰（牛肉大和煮）',
        'kcal'     => 195,
        'unit'     => '缶（90g）',
        'note'     => 'ご飯に合わせやすい。高カロリーで満足感',
        'category' => 'protein',
    ],
    [
        'id'       => 'natto_dried',
        'name'     => 'フリーズドライ納豆',
        'kcal'     => 190,
        'unit'     => '食（20g）',
        'note'     => '大豆たんぱく・食物繊維。腸内環境を整える',
        'category' => 'protein',
    ],
    // ── スープ・汁物 ──
    [
        'id'       => 'freeze_dried_soup',
        'name'     => 'フリーズドライみそ汁',
        'kcal'     => 30,
        'unit'     => '食（6g）',
        'note'     => 'お湯または水で溶ける。塩分・温かさで精神安定',
        'category' => 'soup',
    ],
    [
        'id'       => 'freeze_dried_soup_variety',
        'name'     => 'フリーズドライスープ（洋風）',
        'kcal'     => 35,
        'unit'     => '食（8g）',
        'note'     => 'コーンスープ・ポタージュ等。気分転換に',
        'category' => 'soup',
    ],
    [
        'id'       => 'instant_soup_can',
        'name'     => '缶詰スープ（コーンスープ等）',
        'kcal'     => 90,
        'unit'     => '缶（190g）',
        'note'     => 'そのまま飲める。野菜成分も補給',
        'category' => 'soup',
    ],
    // ── 間食・補助食品 ──
    [
        'id'       => 'chocolate',
        'name'     => 'チョコレート',
        'kcal'     => 560,
        'unit'     => '枚（100g）',
        'note'     => '高エネルギー・精神的安定にも効果的',
        'category' => 'snack',
    ],
    [
        'id'       => 'granola_bar',
        'name'     => 'グラノーラバー・栄養補助食品',
        'kcal'     => 200,
        'unit'     => '本（40g）',
        'note'     => 'カルシウム・鉄分等補える機能性食品',
        'category' => 'snack',
    ],
    [
        'id'       => 'senbei',
        'name'     => '煎餅・米菓',
        'kcal'     => 380,
        'unit'     => '袋（100g）',
        'note'     => '長期保存可能。日本人に馴染みやすい',
        'category' => 'snack',
    ],
    [
        'id'       => 'dried_fruit',
        'name'     => 'ドライフルーツ',
        'kcal'     => 270,
        'unit'     => '袋（100g）',
        'note'     => 'ビタミン・ミネラル・食物繊維を補給',
        'category' => 'snack',
    ],
    [
        'id'       => 'nuts',
        'name'     => 'ナッツ類（ミックスナッツ）',
        'kcal'     => 620,
        'unit'     => '袋（100g）',
        'note'     => '良質な脂質・たんぱく質。腹持ち良い',
        'category' => 'snack',
    ],
    [
        'id'       => 'baby_food',
        'name'     => '離乳食・ベビーフード（レトルト）',
        'kcal'     => 80,
        'unit'     => '食（80g）',
        'note'     => '乳幼児向け。月齢に合わせた種類を備蓄',
        'category' => 'snack',
    ],
    // ── 飲料 ──
    [
        'id'       => 'vegetable_juice',
        'name'     => '野菜ジュース（缶）',
        'kcal'     => 45,
        'unit'     => '缶（190ml）',
        'note'     => '野菜不足を補う。ビタミン・ミネラル補給',
        'category' => 'drink',
    ],
    [
        'id'       => 'sports_drink',
        'name'     => 'スポーツドリンク（ペット）',
        'kcal'     => 50,
        'unit'     => '本（500ml）',
        'note'     => '電解質補給。熱中症・脱水症対策に必須',
        'category' => 'drink',
    ],
    [
        'id'       => 'milk_long_life',
        'name'     => '常温保存牛乳（ロングライフ）',
        'kcal'     => 134,
        'unit'     => '本（200ml）',
        'note'     => 'カルシウム・たんぱく質補給。子ども・高齢者に特に推奨',
        'category' => 'drink',
    ],
];

/**
 * 食事プリセット
 * items の ratio は「1日の総カロリーに占める割合」（合計1.0）
 * 各食品の必要食数 = ceil(総カロリー × ratio ÷ 食品kcal)
 */
$foodPresets = [
    [
        'id'          => 'preset_standard',
        'name'        => '標準バランス型',
        'icon'        => '🍱',
        'description' => 'アルファ米・缶詰・みそ汁を中心とした定番の組み合わせ。カロリー・たんぱく質をバランスよく確保',
        'items'       => [
            ['food_id' => 'alpha_rice_white',   'ratio' => 0.40],
            ['food_id' => 'retort_curry',        'ratio' => 0.20],
            ['food_id' => 'canned_tuna',         'ratio' => 0.20],
            ['food_id' => 'freeze_dried_soup',   'ratio' => 0.05],
            ['food_id' => 'granola_bar',         'ratio' => 0.15],
        ],
    ],
    [
        'id'          => 'preset_no_cooking',
        'name'        => '調理不要型',
        'icon'        => '🥡',
        'description' => '水・火を使わず食べられる食品のみで構成。停電・断水時でも対応可能',
        'items'       => [
            ['food_id' => 'crackers',            'ratio' => 0.25],
            ['food_id' => 'bread_can',           'ratio' => 0.25],
            ['food_id' => 'canned_tuna',         'ratio' => 0.20],
            ['food_id' => 'chocolate',           'ratio' => 0.10],
            ['food_id' => 'nuts',                'ratio' => 0.10],
            ['food_id' => 'dried_fruit',         'ratio' => 0.10],
        ],
    ],
    [
        'id'          => 'preset_family',
        'name'        => '子ども・家族向け',
        'icon'        => '👨‍👩‍👧',
        'description' => '子どもが食べやすい食品を中心に。パン缶・カップ麺・レトルト丼など食べ慣れた味を優先',
        'items'       => [
            ['food_id' => 'retort_rice_pack',    'ratio' => 0.25],
            ['food_id' => 'cup_noodle',          'ratio' => 0.15],
            ['food_id' => 'bread_can',           'ratio' => 0.15],
            ['food_id' => 'retort_rice_bowl',    'ratio' => 0.15],
            ['food_id' => 'canned_chicken',      'ratio' => 0.10],
            ['food_id' => 'granola_bar',         'ratio' => 0.10],
            ['food_id' => 'milk_long_life',      'ratio' => 0.10],
        ],
    ],
    [
        'id'          => 'preset_elderly',
        'name'        => '高齢者・体調不良向け',
        'icon'        => '🧓',
        'description' => '消化が良くやわらかい食品中心。おかゆ・スープ・フリーズドライで塩分・水分も補給',
        'items'       => [
            ['food_id' => 'retort_rice_porridge','ratio' => 0.35],
            ['food_id' => 'freeze_dried_soup',   'ratio' => 0.10],
            ['food_id' => 'instant_soup_can',    'ratio' => 0.10],
            ['food_id' => 'canned_mackerel',     'ratio' => 0.20],
            ['food_id' => 'natto_dried',         'ratio' => 0.10],
            ['food_id' => 'vegetable_juice',     'ratio' => 0.15],
        ],
    ],
    [
        'id'          => 'preset_high_calorie',
        'name'        => '高カロリー・長期備蓄型',
        'icon'        => '💪',
        'description' => '少量で高カロリーを確保。スペースを取らず長期保存可能な食品中心。避難長期化に対応',
        'items'       => [
            ['food_id' => 'nuts',                'ratio' => 0.20],
            ['food_id' => 'chocolate',           'ratio' => 0.15],
            ['food_id' => 'crackers',            'ratio' => 0.20],
            ['food_id' => 'alpha_rice_mixed',    'ratio' => 0.25],
            ['food_id' => 'canned_beef',         'ratio' => 0.20],
        ],
    ],
    [
        'id'          => 'preset_variety',
        'name'        => '飽き防止・バラエティ型',
        'icon'        => '🌈',
        'description' => '食の単調さを防ぎ、精神的安定を保つ多様な食品構成。長期避難・ローリングストックに最適',
        'items'       => [
            ['food_id' => 'alpha_rice_takikomi', 'ratio' => 0.15],
            ['food_id' => 'cup_udon',            'ratio' => 0.10],
            ['food_id' => 'retort_stew',         'ratio' => 0.15],
            ['food_id' => 'retort_pasta_sauce',  'ratio' => 0.10],
            ['food_id' => 'canned_sardine',      'ratio' => 0.10],
            ['food_id' => 'freeze_dried_soup_variety', 'ratio' => 0.05],
            ['food_id' => 'senbei',              'ratio' => 0.10],
            ['food_id' => 'dried_fruit',         'ratio' => 0.10],
            ['food_id' => 'granola_bar',         'ratio' => 0.10],
            ['food_id' => 'sports_drink',        'ratio' => 0.05],
        ],
    ],
];

/**
 * PHPからJavaScriptへデータを渡すためにJSON化
 */
$jsonCalorieData = json_encode($calorieData,   JSON_UNESCAPED_UNICODE);
$jsonWaterData   = json_encode($waterData,     JSON_UNESCAPED_UNICODE);
$jsonFoodItems   = json_encode($foodItems,     JSON_UNESCAPED_UNICODE);
$jsonFoodPresets = json_encode($foodPresets,   JSON_UNESCAPED_UNICODE);
