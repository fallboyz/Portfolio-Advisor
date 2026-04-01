(function () {
    "use strict";

    var FONT = "Pretendard, sans-serif";
    var BLUE = "#093687";
    var GREEN = "#0d9488";
    var RED = "#dc2626";
    var GRAY = "#6b7280";
    var AMBER = "#d97706";

    var SIGNAL_KO = {
        strong_precious: {
            label: "실물 자산 비중 대폭 확대",
            desc: "실물 자산(금/은)이 역사적으로 크게 저평가된 구간. 실물 자산 비중을 크게 늘리는 게 유리."
        },
        mild_precious: {
            label: "실물 자산 비중 확대",
            desc: "실물 자산이 상대적으로 저평가. 실물 자산 쪽에 비중을 좀 더 두는 게 유리한 구간."
        },
        neutral: {
            label: "균형 배분",
            desc: "실물 자산과 ETF 모두 특별히 저평가/고평가 구간이 아님. 기본 비율(50:50) 유지."
        },
        mild_etf: {
            label: "ETF 비중 확대",
            desc: "ETF가 상대적으로 매력적. ETF 쪽에 비중을 좀 더 두는 게 유리한 구간."
        },
        strong_etf: {
            label: "ETF 비중 대폭 확대",
            desc: "실물 자산이 역사적으로 크게 고평가된 구간. ETF 비중을 크게 늘리는 게 유리."
        }
    };

    var ZSCORE_LABELS = {
        return_50y: "50년 수익률",
        return_10y: "10년 수익률",
        return_5y: "5년 수익률",
        price_position: "가격 위치",
        cape: "CAPE",
        gsr: "금은비"
    };

    var currentYears = 1;

    // ── Helpers ──

    function colorByThreshold(v) {
        if (v < -1) return GREEN;
        if (v > 1) return RED;
        return GRAY;
    }

    function colorBySign(v) {
        return v < 0 ? GREEN : RED;
    }

    var defaultLayout = {
        autosize: true,
        font: { family: FONT },
        paper_bgcolor: "white",
        plot_bgcolor: "white",
        margin: { t: 15, b: 30, l: 55, r: 15 },
        modebar: { orientation: "v" }
    };

    var plotlyConfig = { responsive: true, displaylogo: false };

    function mergeLayout(extra) {
        var result = {};
        for (var k in defaultLayout) result[k] = defaultLayout[k];
        for (var k2 in extra) result[k2] = extra[k2];
        return result;
    }

    // ── Init ──

    document.addEventListener("DOMContentLoaded", function () {
        loadLatest();
        loadPrices(currentYears);
        loadGSR();
        loadZscores();
        loadCompositeHistory();

        // Period buttons
        var btns = document.querySelectorAll(".period-btn");
        btns.forEach(function (btn) {
            btn.addEventListener("click", function () {
                btns.forEach(function (b) { b.classList.remove("active"); });
                btn.classList.add("active");
                currentYears = parseInt(btn.dataset.years, 10);
                loadPrices(currentYears);
            });
        });

        // Date selector
        var sel = document.getElementById("analysis-date-select");
        sel.addEventListener("change", function () {
            if (sel.value) loadAnalysis(sel.value);
        });
    });

    // ── Latest Data ──

    function loadLatest() {
        fetch("/api/latest")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    document.getElementById("no-data").style.display = "block";
                    return;
                }
                renderSignalCard(data);
                renderMetrics(data);
                renderGauge(data.r_group || 0);
                loadLatestAnalysis(data.calc_date);
            });
    }

    function renderSignalCard(data) {
        var card = document.getElementById("signal-card");
        var info = SIGNAL_KO[data.signal_label] || SIGNAL_KO.neutral;
        var preciousPct = data.precious_pct || 50;
        var etfPct = 100 - preciousPct;

        document.getElementById("signal-label").textContent = info.label;
        document.getElementById("signal-desc").textContent = info.desc;
        document.getElementById("precious-pct").textContent = preciousPct;
        document.getElementById("gold-ratio").textContent =
            "금 " + (data.gold_pct || 50) + " : 은 " + (data.silver_pct || 50);
        document.getElementById("etf-pct").textContent = etfPct;
        document.getElementById("etf-ratio").textContent =
            "S&P " + (data.sp500_pct || 60) + " : 나스닥 " + (data.ndx_pct || 40);
        card.style.display = "block";
    }

    function renderMetrics(data) {
        var row = document.getElementById("metrics-row");
        var rGroup = data.r_group || 0;
        var sPrecious = data.s_precious || 0;
        var sEtf = data.s_etf || 0;

        document.getElementById("r-group-value").textContent = rGroup.toFixed(2);
        document.getElementById("r-group-value").style.color = colorByThreshold(rGroup);

        document.getElementById("precious-value").textContent = sPrecious.toFixed(2);
        document.getElementById("precious-value").style.color = colorBySign(sPrecious);
        document.getElementById("precious-hint").textContent =
            "금 " + (data.s_gold || 0).toFixed(2) + " / 은 " + (data.s_silver || 0).toFixed(2);

        document.getElementById("etf-value").textContent = sEtf.toFixed(2);
        document.getElementById("etf-value").style.color = colorBySign(sEtf);
        document.getElementById("etf-hint").textContent =
            "S&P " + (data.s_sp500 || 0).toFixed(2) + " / 나스닥 " + (data.s_ndx || 0).toFixed(2);

        row.style.display = "flex";
    }

    function renderGauge(value) {
        var color = value < -1 ? GREEN : (value > 1 ? RED : GRAY);
        var data = [{
            type: "indicator",
            mode: "gauge+number",
            value: value,
            number: { font: { size: 40, family: FONT } },
            gauge: {
                axis: { range: [-4, 4], tickfont: { size: 11 } },
                bar: { color: color, thickness: 0.6 },
                steps: [
                    { range: [-4, -2], color: "#d1fae5" },
                    { range: [-2, -1], color: "#ecfdf5" },
                    { range: [-1, 1], color: "#f3f4f6" },
                    { range: [1, 2], color: "#fef2f2" },
                    { range: [2, 4], color: "#fee2e2" }
                ]
            }
        }];
        var layout = mergeLayout({
            height: 200,
            margin: { t: 15, b: 35, l: 25, r: 25 },
            annotations: [
                {
                    x: 0.13, y: -0.12, text: "실물 자산 유리", showarrow: false,
                    font: { size: 11, color: GREEN, family: FONT }, xref: "paper", yref: "paper"
                },
                {
                    x: 0.87, y: -0.12, text: "ETF 유리", showarrow: false,
                    font: { size: 11, color: RED, family: FONT }, xref: "paper", yref: "paper"
                }
            ]
        });
        Plotly.newPlot("gauge-chart", data, layout, { responsive: true, displaylogo: false, displayModeBar: false });
    }

    // ── Latest Comment ──

    function loadLatestAnalysis(calcDate) {
        if (!calcDate) return;
        var dateStr = calcDate.substring(0, 10);
        fetch("/api/analysis/" + dateStr)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) return;
                var comp = data.composite;
                var info = SIGNAL_KO[comp.signal_label] || SIGNAL_KO.neutral;
                var preciousPct = comp.precious_pct || 50;
                var etfPct = 100 - preciousPct;

                // Data section from composite numbers
                var dataLines = [];
                dataLines.push("비율: 실물 자산 " + preciousPct + "% (금 " + (comp.gold_pct || 50) +
                    "% / 은 " + (comp.silver_pct || 50) + "%) | ETF " + etfPct +
                    "% (S&P " + (comp.sp500_pct || 60) + "% / 나스닥 " + (comp.ndx_pct || 40) + "%)");
                dataLines.push("그룹 R=" + (comp.r_group || 0).toFixed(2) +
                    " / 실물 점수=" + (comp.s_precious || 0).toFixed(2) +
                    " / ETF 점수=" + (comp.s_etf || 0).toFixed(2));
                dataLines.push("금=" + (comp.s_gold || 0).toFixed(2) +
                    " / 은=" + (comp.s_silver || 0).toFixed(2) +
                    " / S&P=" + (comp.s_sp500 || 0).toFixed(2) +
                    " / 나스닥=" + (comp.s_ndx || 0).toFixed(2));
                dataLines.push("은 낙폭=" + (comp.dd_silver || 0).toFixed(1) +
                    "% / ETF 낙폭=" + (comp.dd_etf || 0).toFixed(1) + "%");

                // Try to parse comment sections for trend/conclusion
                var trendText = "(MCP 분석 데이터 없음)";
                var conclusionText = info.desc;

                if (data.comments && data.comments.length > 0) {
                    var fullText = data.comments.map(function (c) { return c.content; }).join("\n\n");
                    var parsed = parseCommentSections(fullText);
                    if (parsed.trend) trendText = parsed.trend;
                    if (parsed.conclusion) conclusionText = parsed.conclusion;
                }

                document.getElementById("latest-data").textContent = dataLines.join("\n");
                document.getElementById("latest-trend").textContent = trendText;
                document.getElementById("latest-conclusion").textContent = conclusionText;

                // Meta
                var metaText = dateStr;
                if (data.comments && data.comments.length > 0) {
                    var lastComment = data.comments[data.comments.length - 1];
                    metaText = lastComment.date.substring(0, 16).replace("T", " ") + " / " +
                        (lastComment.author === "system" ? "자동 분석" : lastComment.author);
                }
                document.getElementById("latest-analysis-meta").textContent = metaText;
                document.getElementById("latest-analysis").style.display = "block";
            });
    }

    // ── Price Charts ──

    function loadPrices(years) {
        var symbols = [
            { key: "SILVER", div: "chart-silver", name: "은" },
            { key: "GOLD", div: "chart-gold", name: "금" },
            { key: "SP500", div: "chart-sp500", name: "S&P 500" },
            { key: "NDX", div: "chart-ndx", name: "나스닥 100" }
        ];
        symbols.forEach(function (s) {
            fetch("/api/prices/" + s.key + "?years=" + years)
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    document.getElementById("price-section").style.display = "block";
                    renderPriceChart(s.div, data, s.name);
                });
        });
    }

    function renderPriceChart(divId, data, title) {
        if (!data.dates || data.dates.length === 0) {
            document.getElementById(divId).innerHTML =
                '<div style="text-align:center;padding:2rem;color:#999;">데이터 없음</div>';
            return;
        }
        var traces = [{
            x: data.dates,
            y: data.closes,
            type: "scatter",
            mode: "lines",
            name: title,
            line: { width: 1.5, color: BLUE }
        }];
        var layout = mergeLayout({
            height: 320,
            yaxis: { title: "가격 ($)", gridcolor: "#f0f0f0", zeroline: false },
            xaxis: { gridcolor: "#f0f0f0", zeroline: false }
        });
        Plotly.newPlot(divId, traces, layout, plotlyConfig);
    }

    // ── GSR ──

    function loadGSR() {
        fetch("/api/indicators/GSR")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.dates || data.dates.length === 0) return;
                document.getElementById("gsr-section").style.display = "block";
                renderGSRChart(data);
            });
    }

    function renderGSRChart(data) {
        var traces = [{
            x: data.dates,
            y: data.values,
            type: "scatter",
            mode: "lines",
            name: "금/은 비율",
            line: { width: 1.5, color: AMBER },
            fill: "tozeroy",
            fillcolor: "rgba(217, 119, 6, 0.05)"
        }];
        var layout = mergeLayout({
            height: 350,
            margin: { t: 15, b: 30, l: 55, r: 15 },
            yaxis: { title: "비율", gridcolor: "#f0f0f0", zeroline: false },
            xaxis: { gridcolor: "#f0f0f0", zeroline: false },
            shapes: [
                {
                    type: "line", x0: 0, x1: 1, xref: "paper",
                    y0: 80, y1: 80, line: { dash: "dot", color: GREEN, width: 1 }
                },
                {
                    type: "line", x0: 0, x1: 1, xref: "paper",
                    y0: 50, y1: 50, line: { dash: "dot", color: RED, width: 1 }
                }
            ],
            annotations: [
                {
                    x: 1, xref: "paper", y: 80, text: "80: 은 저평가",
                    showarrow: false, font: { size: 10 }, xanchor: "right"
                },
                {
                    x: 1, xref: "paper", y: 50, text: "50: 은 고평가",
                    showarrow: false, font: { size: 10 }, xanchor: "right"
                }
            ]
        });
        Plotly.newPlot("chart-gsr", traces, layout, plotlyConfig);
    }

    // ── Z-Score Heatmap ──

    function loadZscores() {
        fetch("/api/zscores")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.symbols || data.symbols.length === 0) return;
                document.getElementById("zscore-section").style.display = "block";
                renderZscoreHeatmap(data);
            });
    }

    function renderZscoreHeatmap(data) {
        var yLabels = data.metrics.map(function (m) { return ZSCORE_LABELS[m] || m; });
        var textArr = data.values.map(function (row) {
            return row.map(function (v) { return v === null ? "" : v.toFixed(2); });
        });
        var traces = [{
            z: data.values,
            x: data.symbols,
            y: yLabels,
            type: "heatmap",
            colorscale: [[0, GREEN], [0.5, "#f3f4f6"], [1, RED]],
            zmid: 0,
            text: textArr,
            texttemplate: "%{text}",
            textfont: { size: 12 },
            colorbar: { title: "Z", thickness: 12 },
            hoverongaps: false
        }];
        var layout = mergeLayout({
            height: 320,
            margin: { t: 15, b: 30, l: 110, r: 20 }
        });
        Plotly.newPlot("chart-zscore", traces, layout, plotlyConfig);
    }

    // ── Composite History ──

    function loadCompositeHistory() {
        fetch("/api/history")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!data.history || data.history.length === 0) return;
                document.getElementById("composite-section").style.display = "block";
                document.getElementById("analysis-section").style.display = "block";
                renderCompositeHistory(data.history);
                populateDateSelector(data.dates);
            });
    }

    function renderCompositeHistory(history) {
        var dates = history.map(function (h) { return h.analyzed_at || h.calc_date; });
        var lineMode = dates.length === 1 ? "lines+markers" : "lines";
        var traces = [
            {
                x: dates, y: history.map(function (h) { return h.s_precious; }),
                type: "scatter", mode: lineMode, name: "실물 자산 점수",
                line: { color: AMBER, width: 1.5 }, marker: { size: 6 }
            },
            {
                x: dates, y: history.map(function (h) { return h.s_etf; }),
                type: "scatter", mode: lineMode, name: "ETF 점수",
                line: { color: "blue", width: 1.5 }, marker: { size: 6 }
            },
            {
                x: dates, y: history.map(function (h) { return h.r_group; }),
                type: "scatter", mode: lineMode, name: "R 점수 (실물 자산-ETF)",
                line: { color: "black", width: 2 }, marker: { size: 7 }
            }
        ];
        var layout = mergeLayout({
            height: 400,
            margin: { t: 15, b: 30, l: 55, r: 15 },
            yaxis: { title: "점수", gridcolor: "#f0f0f0", zeroline: false },
            xaxis: { type: "date", tickformat: "%Y-%m-%d %H:%M", gridcolor: "#f0f0f0", zeroline: false },
            shapes: [
                { type: "rect", x0: 0, x1: 1, xref: "paper", y0: -4, y1: -2, fillcolor: "green", opacity: 0.05, line: { width: 0 } },
                { type: "rect", x0: 0, x1: 1, xref: "paper", y0: -2, y1: -1, fillcolor: "green", opacity: 0.03, line: { width: 0 } },
                { type: "rect", x0: 0, x1: 1, xref: "paper", y0: 1, y1: 2, fillcolor: "red", opacity: 0.03, line: { width: 0 } },
                { type: "rect", x0: 0, x1: 1, xref: "paper", y0: 2, y1: 4, fillcolor: "red", opacity: 0.05, line: { width: 0 } }
            ]
        });
        Plotly.newPlot("chart-composite", traces, layout, plotlyConfig);
    }

    // ── Date Selector + Analysis ──

    function populateDateSelector(dates) {
        var sel = document.getElementById("analysis-date-select");
        dates.forEach(function (entry) {
            var opt = document.createElement("option");
            var calcDate = entry.calc_date;
            var analyzedAt = entry.analyzed_at;
            opt.value = calcDate;
            opt.textContent = calcDate + "  " + analyzedAt.substring(11, 16);
            sel.appendChild(opt);
        });
    }

    function loadAnalysis(dateStr) {
        fetch("/api/analysis/" + dateStr)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) return;
                renderAnalysis(data);
                document.getElementById("analysis-detail").style.display = "block";
            });
    }

    function renderAnalysis(data) {
        var comp = data.composite;
        var info = SIGNAL_KO[comp.signal_label] || SIGNAL_KO.neutral;
        var preciousPct = comp.precious_pct || 50;
        var etfPct = 100 - preciousPct;

        // Parse comments for sections
        var dataSection = "";
        var trendSection = "";
        var conclusionSection = "";

        if (data.comments && data.comments.length > 0) {
            var fullText = data.comments.map(function (c) { return c.content; }).join("\n\n");
            var parsed = parseCommentSections(fullText);
            dataSection = parsed.data;
            trendSection = parsed.trend;
            conclusionSection = parsed.conclusion;
        }

        // Fallback: build data section from composite numbers
        if (!dataSection) {
            var lines = [];
            lines.push(info.label + " - 실물 " + preciousPct + "% / ETF " + etfPct + "%");
            lines.push("");
            lines.push("비율: 실물 자산 " + preciousPct + "% (금 " + (comp.gold_pct || 50) +
                "% / 은 " + (comp.silver_pct || 50) + "%) | ETF " + etfPct +
                "% (S&P " + (comp.sp500_pct || 60) + "% / 나스닥 " + (comp.ndx_pct || 40) + "%)");
            lines.push("");
            lines.push("수치:");
            lines.push("  그룹 R=" + (comp.r_group || 0).toFixed(2) +
                " / 실물 점수=" + (comp.s_precious || 0).toFixed(2) +
                " / ETF 점수=" + (comp.s_etf || 0).toFixed(2));
            lines.push("  금=" + (comp.s_gold || 0).toFixed(2) +
                " / 은=" + (comp.s_silver || 0).toFixed(2) +
                " / S&P=" + (comp.s_sp500 || 0).toFixed(2) +
                " / 나스닥=" + (comp.s_ndx || 0).toFixed(2));
            dataSection = lines.join("\n");
        }

        if (!trendSection) trendSection = "(MCP 분석 데이터 없음)";
        if (!conclusionSection) conclusionSection = info.desc;

        setContent("analysis-data", dataSection);
        setContent("analysis-trend", trendSection);
        setContent("analysis-conclusion", conclusionSection);
    }

    function parseCommentSections(text) {
        var result = { data: "", trend: "", conclusion: "" };
        var dataMatch = text.match(/데이터 분석:\s*\n([\s\S]*?)(?=시장 동향:|종합 판단:|$)/);
        var trendMatch = text.match(/시장 동향:\s*\n([\s\S]*?)(?=종합 판단:|$)/);
        var conclusionMatch = text.match(/종합 판단:\s*\n([\s\S]*?)$/);

        if (dataMatch) result.data = dataMatch[1].trim();
        if (trendMatch) result.trend = trendMatch[1].trim();
        if (conclusionMatch) result.conclusion = conclusionMatch[1].trim();

        return result;
    }

    function setContent(id, text) {
        var el = document.getElementById(id);
        // Clear existing content divs
        var existing = el.querySelector(".content");
        if (existing) existing.remove();
        var div = document.createElement("div");
        div.className = "content";
        div.textContent = text;
        el.appendChild(div);
    }

})();
