"""Offline, aggregate-only HTML for M3.11 five-policy seed-stability reports.

No JavaScript, third-party fonts, CDN or seat-private replay data. These bars
and heatmaps visualize prototype statistics; they are not official win rates.
"""
from __future__ import annotations

from html import escape
from typing import Any

LABELS = {
    "baseline": "独立牌形基线",
    "advanced": "进阶",
    "challenge_no_ukeire": "关闭有效进张",
    "challenge_no_pressure": "关闭弱风险平局",
    "challenge": "完整挑战",
}
CONTRAST_LABELS = {
    "challenge_vs_challenge_no_pressure": "完整挑战 − 关闭弱风险",
    "challenge_vs_challenge_no_ukeire": "完整挑战 − 关闭有效进张",
    "challenge_no_pressure_vs_advanced": "仅有效进张 − 进阶",
    "challenge_no_ukeire_vs_advanced": "仅弱风险 − 进阶",
    "challenge_vs_baseline": "完整挑战 − 独立基线",
}


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value*100:.1f}%"


def _pp(value: float | None) -> str:
    return "—" if value is None else f"{value*100:+.2f} pp"


def _class(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _bar_chart(report: dict[str, Any], metric: str, heading: str) -> str:
    """SVG percentage bars generated only from aggregate policy metrics."""
    bar_left, width = 198, 405
    items = []
    for idx, policy in enumerate(report["opponents"]):
        y = 38 + idx * 49
        value = report["levels"][policy][metric]
        frac = max(0.0, min(1.0, float(value))) if value is not None else 0.0
        label = escape(LABELS.get(policy, policy))
        fill = "#31af93" if policy == "challenge" else "#6c93bc"
        items.extend((
            f'<text x="10" y="{y+16}" class="bar-label">{label}</text>',
            f'<rect x="{bar_left}" y="{y}" width="{width}" height="21" rx="5" class="bar-bg"/>',
            f'<rect x="{bar_left}" y="{y}" width="{width*frac:.1f}" height="21" rx="5" fill="{fill}"/>',
            f'<text x="{bar_left+width+12}" y="{y+16}" class="bar-value">{escape(_pct(value))}</text>',
        ))
    height = 50 + len(report["opponents"])*49
    return (
        '<section class="panel"><h2>'+escape(heading)+'</h2>'
        '<svg role="img" aria-label="'+escape(heading)+'" '
        f'viewBox="0 0 700 {height}" xmlns="http://www.w3.org/2000/svg">'
        '<style>.bar-label,.bar-value{fill:#dbe7ee;font-size:13px;'
        'font-family:system-ui,sans-serif}.bar-bg{fill:#2c4050}</style>'
        + ''.join(items)+'</svg></section>'
    )


def _heatmap(report: dict[str, Any], metric: str, heading: str) -> str:
    analysis = report["seed_analysis"]
    seeds = analysis["per_seed_differences"]
    comparisons = list(CONTRAST_LABELS)
    thead = ''.join(
        '<th scope="col">'+escape(CONTRAST_LABELS[name])+'</th>'
        for name in comparisons
    )
    rows = []
    for item in seeds:
        cells = []
        for name in comparisons:
            value = item["differences"][name][metric]
            cells.append(
                '<td class="'+_class(value)+'" title="每个独立种子的五局分组差值">'
                + escape(_pp(value))+'</td>'
            )
        rows.append(
            '<tr><th scope="row">'+escape(str(item["seed"]))+'</th>'
            + ''.join(cells)+'</tr>'
        )
    return (
        '<section class="panel"><h2>'+escape(heading)+'</h2>'
        '<p class="hint">单位：百分点（pp）。正号表示前一策略的指标较高；'
        '这是同洗牌种子的描述性比较，并不是独立反事实。</p>'
        '<div class="table-scroll"><table><thead><tr><th scope="col">种子</th>'
        + thead + '</tr></thead><tbody>'+''.join(rows)
        + '</tbody></table></div></section>'
    )


def _stability(report: dict[str, Any]) -> str:
    analysis = report["seed_analysis"]
    counts = analysis["direction_counts"]
    sensitivity = analysis["leave_one_seed_out"]
    rows = []
    for contrast, label in CONTRAST_LABELS.items():
        wins = counts[contrast]["win_event_fraction"]
        best = counts[contrast]["local_optimal_fraction"]
        loo = (sensitivity or {}).get(contrast, {}).get("win_event_fraction")
        if loo is None:
            interval = '—（独立种子不足5个）'
        else:
            interval = f'{_pp(loo["min"])} 至 {_pp(loo["max"])}'
        rows.append(
            '<tr><th scope="row">'+escape(label)+'</th>'
            f'<td>{wins["positive"]} / {wins["negative"]} / {wins["tied"]}'
            f' / {wins["undefined"]}</td>'
            f'<td>{best["positive"]} / {best["negative"]} / {best["tied"]}'
            f' / {best["undefined"]}</td>'
            '<td>'+escape(interval)+'</td></tr>'
        )
    return (
        '<section class="panel"><h2>跨种子方向一致性</h2>'
        '<p class="hint">“正 / 负 / 相同 / 未定义”按独立洗牌种子计数，'
        '不把同种子五局当成五份样本。留一法是去掉一个完整种子分组后'
        '重新汇总比率的最小与最大差异，只用于观察敏感性。</p>'
        '<div class="table-scroll"><table><thead><tr>'
        '<th scope="col">对照</th><th scope="col">胡牌事件方向</th>'
        '<th scope="col">局部最优方向</th><th scope="col">留一种子后胡牌事件差值</th>'
        '</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div></section>'
    )


def _pressure_panel(report: dict[str, Any]) -> str:
    """Only anonymized counts. The unplayed shadow tile stays concealed."""
    stats = report.get("pressure_diagnostics")
    if stats is None:
        return ""
    names = {
        "challenge": "完整挑战",
        "challenge_no_pressure": "关闭弱风险平局",
    }
    columns = (
        ("decisions", "切牌决策"),
        ("effective_ties", "进张并列"),
        ("pressure_present", "存在副露压力"),
        ("pressure_discriminates", "压力分数区分候选"),
        ("would_change", "启停规则会改变切牌"),
        ("actual_changed", "本策略实际受规则改变"),
        ("games_with_would_change", "至少一次改变的对局"),
        ("wins_in_changed_games", "这些对局中的胡牌事件"),
        ("deal_ins_in_changed_games", "这些对局中的放铳责任"),
    )
    heading = "".join(
        "<th scope=\"col\">"+escape(label)+"</th>"
        for _,label in columns
    )
    rows = []
    for policy in ("challenge","challenge_no_pressure"):
        row = stats[policy]
        rows.append(
            "<tr><th scope=\"row\">"+escape(names[policy])+"</th>"
            + "".join("<td>"+str(row[key])+"</td>" for key,_ in columns)
            + "</tr>"
        )
    return (
        '<section class="panel"><h2>M3.12 · 公开副露弱风险规则触发诊断</h2>'
        '<p class="hint">对同一个真实切牌局面，同时计算启用与关闭弱风险平局规则的候选选择。'
        '只有实际两个切牌不同才记录为“会改变”；从不将未出牌的候选牌公布。'
        '“这些对局中的胡牌/放铳”只是相关性分组，不是该规则造成的收益或损失。</p>'
        '<div class="table-scroll"><table><thead><tr><th scope="col">策略</th>'
        + heading+'</tr></thead><tbody>'+''.join(rows)
        +'</tbody></table></div></section>'
    )


def render_ablation_html(report: dict[str, Any]) -> str:
    """Render a self-contained dashboard from M3.11 aggregate JSON.

    Intentional allowlist: no traces, opponent concealed hands, wall or
    downloadable private data. Requires an M3.11-enriched M3.10 report.
    """
    if (report.get("protocol") !=
            "five_policy_four_seat_incomplete_block_ablation_v1" or
            "seed_analysis" not in report):
        raise ValueError("expected an M3.11-enriched ablation report")
    seeds = report["independent_shuffle_seeds"]
    seed_start = report["seed_start"]
    games = report["games"]
    interval = report.get("interval_status", "unknown")
    stats = (
        f'<strong>{seeds}</strong> 个独立洗牌种子'
        f'<span>／ {games} 场相关四人对局</span>'
        f'<span>／起始种子 {seed_start}</span>'
    )
    notice = (
        '<p class="notice">注意：这些图展示草案规则下的胡牌事件比例、'
        '放铳及同源牌效指标，不是正式结算胜率。'
        '每个独立种子的5场轮换属于同一组，不能当成5个独立样本。'
        '少于5个独立种子不提供 Bootstrap 区间，5个也仅作探索。</p>'
    )
    extra = ('已计算探索性整组 Bootstrap 区间；'
             '请结合 CSV 和 JSON 检查其口径。'
             if interval == "exploratory_only" else
             '独立种子不足5个，未生成区间。')
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MahTrain M3.11 · 多种子 AI 消融分析</title>'
        '<style>'
        ':root{color-scheme:dark;font-family:system-ui,"Microsoft YaHei",sans-serif;'
        'background:#0b1722;color:#e6eff5}'
        '*{box-sizing:border-box}body{margin:0;padding:30px 20px;line-height:1.6}'
        'main{max-width:1180px;margin:auto}h1{margin:5px 0;font-size:30px}'
        'h2{font-size:19px;margin:0 0 14px}p{margin:6px 0 14px}'
        '.eyebrow{letter-spacing:.08em;color:#8db8c4;font-size:13px;font-weight:700}'
        '.metrics{display:flex;gap:12px;flex-wrap:wrap;color:#a3b5c1}'
        '.metrics strong{font-size:24px;color:white}.notice{border-left:3px solid #dda865;'
        'background:#23313d;padding:13px 17px;margin:22px 0}'
        '.panel{border:1px solid #2e4657;background:#152534;border-radius:13px;'
        'padding:20px 22px;margin:18px 0}.panel svg{max-width:100%;height:auto;display:block}'
        '.hint{color:#a9c0cb;font-size:13px}.table-scroll{overflow-x:auto}'
        'table{width:100%;border-collapse:collapse;font-size:13px;min-width:800px}'
        'td,th{padding:11px 10px;text-align:center;border-bottom:1px solid #304858}'
        'th:first-child{text-align:left;white-space:nowrap}thead{color:#a3bac6}'
        'td.positive{background:#183e39;color:#a8e2d2}'
        'td.negative{background:#493035;color:#ffb4b6}'
        'td.neutral{background:#263d4a;color:#dce5eb}'
        'td.unknown{color:#9cacb7}footer{margin:28px 0;color:#8ca3b1;font-size:12px}'
        '</style></head><body><main>'
        '<div class="eyebrow">MAHTRAIN / EXPLORATORY BENCHMARK</div>'
        '<h1>M3.11 · 多种子消融分析</h1><div class="metrics">'
        + stats + '</div>' + notice
        + '<p class="hint">'+escape(extra)+'</p>'
        + _bar_chart(report, "win_event_fraction",
                     "胡牌事件数 / 策略出场次数（非正式胜率）")
        + _bar_chart(report, "local_optimal_fraction",
                     "内部裁判评出的切牌局部最优率")
        + _heatmap(report, "win_event_fraction", "逐种子 · 胡牌事件差值")
        + _heatmap(report, "local_optimal_fraction", "逐种子 · 局部最优差值")
        + _stability(report)
        + _pressure_panel(report)
        + '<footer>仅使用汇总统计生成 · 不包含对手暗手、牌墙与密封响应 '
          '· 请勿将探索性区间解释为正式获胜概率。</footer>'
        '</main></body></html>\n'
    )
