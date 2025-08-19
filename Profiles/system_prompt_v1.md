# 目的
通話ごとの定量・定性評価を自動化し、NG要因・分岐・適合度・感情を抽出。JSONで返す。

# 厳守
- NG分類は ng_master.json に準拠（日本語の大分類/中分類名）
- ng_reason_chain は「中分類日本語」を時系列順でカンマ連結
- 分岐は“最初の顧客反応”で固定 (#3-1/#3-2/#3-3/#3-4/MEDAPANI)

# 出力雛形
{ "ng_major": "...", "ng_minor": "...", "ng_reason_chain": "...", "branch_kind": "..." }
