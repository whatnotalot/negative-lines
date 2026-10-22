"""
Generates publication-quality Demo Video Script & Storyboard PDF for Project Negative Lines
using KaTeX, Google Fonts, and Headless Chrome print-to-PDF.
"""

import os
import subprocess
import shutil

OUTPUT_DIR = "/Users/technano/agy2-projects/2026.10.OSI Hackathon/For Video"
REPO_DOCS_DIR = "/Users/technano/agy2-projects/2026.10.OSI Hackathon/Negative Lines/docs"
PDF_NAME = "Negative_Lines_Demo_Video_Script_and_Storyboard.pdf"

HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Project Negative Lines: 3.5-Minute Demo Video Script & Storyboard</title>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Source+Sans+3:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">

<style>
@page {
    size: letter;
    margin: 15mm 15mm 17mm 15mm;
    @bottom-center {
        content: "Project Negative Lines · Demo Video Production Storyboard · Page " counter(page) " of 3";
        font-family: 'Source Sans 3', sans-serif;
        font-size: 8pt;
        color: #64748b;
    }
}

* {
    box-sizing: border-box;
}

body {
    font-family: 'Source Sans 3', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 8.5pt;
    line-height: 1.40;
    color: #1e293b;
    background: #ffffff;
    margin: 0;
    padding: 0;
}

/* Header Container */
.doc-header {
    border-bottom: 2pt solid #0f172a;
    padding-bottom: 6pt;
    margin-bottom: 9pt;
    text-align: center;
}

.doc-tag {
    font-size: 7.2pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #2563eb;
    margin-bottom: 2pt;
}

.doc-title {
    font-family: 'Libre Baskerville', serif;
    font-size: 15.5pt;
    font-weight: 700;
    color: #0f172a;
    line-height: 1.22;
    margin: 0 0 4pt 0;
}

.doc-subtitle {
    font-size: 8.6pt;
    color: #475569;
    margin-bottom: 5pt;
}

.badge-row {
    display: flex;
    justify-content: center;
    gap: 5pt;
    flex-wrap: wrap;
}

.badge {
    font-size: 7pt;
    font-weight: 600;
    padding: 1.5pt 5.5pt;
    border-radius: 999px;
    background: #f1f5f9;
    color: #334155;
    border: 1px solid #cbd5e1;
}

.badge-highlight {
    background: #eff6ff;
    color: #1d4ed8;
    border-color: #bfdbfe;
}

/* Context Callout Box */
.context-card {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-left: 3.5pt solid #2563eb;
    padding: 6pt 9pt;
    margin-bottom: 9pt;
    border-radius: 0 4px 4px 0;
}

.context-card h3 {
    margin: 0 0 3pt 0;
    font-size: 8.6pt;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.context-card p {
    margin: 0 0 3pt 0;
    font-size: 8pt;
    color: #334155;
}

.context-card ul {
    margin: 0;
    padding-left: 13pt;
    font-size: 7.9pt;
    color: #334155;
}

.context-card li {
    margin-bottom: 1.5pt;
}

/* Storyboard Tables */
h2.section-header {
    font-size: 10.5pt;
    font-weight: 700;
    color: #0f172a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 2pt;
    margin: 9pt 0 6pt 0;
    break-after: avoid;
    page-break-after: avoid;
}

.scene-block {
    margin-bottom: 8pt;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    overflow: hidden;
    break-inside: avoid;
    page-break-inside: avoid;
}

.scene-header {
    background: #0f172a;
    color: #ffffff;
    padding: 3.5pt 7pt;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 8pt;
    font-weight: 700;
}

.scene-time {
    background: #2563eb;
    padding: 1pt 5pt;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 7.2pt;
}

.scene-body {
    display: grid;
    grid-template-columns: 31% 45% 24%;
    background: #ffffff;
}

.scene-col {
    padding: 5pt 7pt;
    border-right: 1px solid #e2e8f0;
}

.scene-col:last-child {
    border-right: none;
    background: #fafafa;
}

.scene-col-title {
    font-size: 7pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #64748b;
    margin-bottom: 2.5pt;
    border-bottom: 0.5pt solid #f1f5f9;
    padding-bottom: 1pt;
}

.vo-text {
    font-family: 'Libre Baskerville', Georgia, serif;
    font-size: 8.1pt;
    color: #0f172a;
    line-height: 1.38;
}

.visual-action {
    font-size: 7.8pt;
    color: #1e293b;
    line-height: 1.32;
}

.visual-action strong {
    color: #0369a1;
}

.osd-text {
    font-size: 7.5pt;
    color: #475569;
    line-height: 1.28;
}

.osd-badge {
    display: inline-block;
    background: #e0f2fe;
    color: #0369a1;
    font-family: 'JetBrains Mono', monospace;
    font-size: 6.8pt;
    font-weight: 600;
    padding: 1pt 3.5pt;
    border-radius: 3px;
    margin-top: 2.5pt;
}

/* Feature Comparison Table on Page 2 */
table.comp-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.6pt;
    margin: 6pt 0 8pt 0;
    break-inside: avoid;
}

table.comp-table th {
    background: #0f172a;
    color: #ffffff;
    padding: 3.5pt 5pt;
    font-weight: 700;
    text-align: left;
}

table.comp-table td {
    border: 1px solid #e2e8f0;
    padding: 3pt 5pt;
    color: #334155;
    vertical-align: top;
}

/* Checklist Table */
table.checklist-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.6pt;
    margin-top: 5pt;
    break-inside: avoid;
}

table.checklist-table th {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    padding: 3pt 5pt;
    font-weight: 700;
    text-align: left;
    color: #0f172a;
}

table.checklist-table td {
    border: 1px solid #e2e8f0;
    padding: 3pt 5pt;
    color: #334155;
    vertical-align: top;
}

.page-break {
    page-break-after: always;
    break-after: page;
}
</style>
</head>

<body>

<!-- ========================================== PAGE 1 ========================================== -->
<div class="doc-header">
  <div class="doc-tag">OSI Hackathon 2026 &middot; Demonstration Video Production Package</div>
  <h1 class="doc-title">Project Negative Lines: 3.5-Minute Demo Video Script & Storyboard</h1>
  <div class="doc-subtitle">Hand-Annotated Gold Data Reconciliation &middot; Manual Engineering vs. Automated Antigravity AI &middot; Green PFAS Compliance</div>
  <div class="badge-row">
    <span class="badge badge-highlight">Target Duration: 3 min 30 sec (210s)</span>
    <span class="badge">Spoken Words: ~460 words (~132 wpm)</span>
    <span class="badge">Full 1080p Screencast (16:9)</span>
    <span class="badge">Dual-Track Streamlit Architecture</span>
  </div>
</div>

<div class="context-card">
  <h3>Project Lineage & Technical Distinction (Crucial Context for Presenters)</h3>
  <p>
    <strong>1. Ground Truth Origin:</strong> Two researchers (<strong>Akhila</strong> and <strong>Kathe</strong>) independently hand-annotated 10 semiconductor negative-resist patents. Automated discrepancy comparison auditing then cross-verified and resolved conflicting entries (text vs. table conflicts, stoichiometry, units) into a 100% consensus Master Reconciled Gold Set (239 formulation records).
  </p>
  <p>
    <strong>2. Automated Compliance Screening:</strong> The reconciled database was evaluated through an automated regulatory screener (OECD PFAS, EU REACH Annex XVII, US TSCA) to isolate persistent fluorinated chemistries.
  </p>
  <p>
    <strong>3. The Two Modeling & Implementation Pathways:</strong>
  </p>
  <ul>
    <li><strong>Manual Track (Manual Evaluation & Coding):</strong> The Bayesian optimization, surrogate modeling, stoichiometric evaluations, and physics calculations were designed, hand-coded, and manually executed step-by-step by human engineers—giving process experts granular control without reliance on automated black-box loops.</li>
    <li><strong>Automated Track (Autonomous Antigravity Agent):</strong> The entire end-to-end pipeline—Gaussian Process fitting with a Mat&eacute;rn 5/2 kernel, constrained Expected Improvement acquisition, epistemic uncertainty quantification (&plusmn;1.96&sigma;), and automated green substitution—was constructed and automated autonomously by <strong>Antigravity</strong>.</li>
  </ul>
</div>

<h2 class="section-header">Demo Video Storyboard (Part I: Introduction & Data Foundation)</h2>

<!-- SCENE 1 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 1: The Nano-Lithography Dilemma & Regulatory PFAS Cliff</span>
    <span class="scene-time">0:00 – 0:35 (35 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        Open on full-screen capture of Streamlit portal with <strong>Dark Enterprise Sidebar</strong>.<br>
        Mouse hovers over <strong>KPI Metric Cards</strong>: 14 Standardized Records, Target LWR &le; 4.5 nm, 100% PFAS-Free.<br>
        Show hero badge: <em>OSI Hackathon 2026 &middot; Project Negative Lines</em>.
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "In advanced semiconductor manufacturing, patterning sub-20-nanometer features requires negative-tone photoresists with exceptional line-width roughness and extreme sensitivity.<br><br>
        Historically, achieving this demanded months of trial-and-error e-beam fab trials and heavy reliance on perfluorinated 'forever chemicals'—PFAS. With impending global bans from the OECD and EU REACH, chipmakers face an urgent crisis: eliminate PFAS without sacrificing sub-5-nanometer resolution.<br><br>
        This is <strong>Project Negative Lines</strong>—an end-to-end platform bridging verified empirical data, manual modeling, and autonomous AI optimization."
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Lower-Third:</strong><br>
        Project Negative Lines<br>
        <em>AI & Manual Lithography Platform</em><br>
        <span class="osd-badge">LWR &le; 4.50 nm</span>
        <span class="osd-badge">100% PFAS-Free</span><br>
        <em>Pacing:</em> Confident, measured tone.
      </div>
    </div>
  </div>
</div>

<!-- SCENE 2 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 2: Hand Annotation to Automated Machine Reconciliation</span>
    <span class="scene-time">0:35 – 1:10 (35 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        In the main dashboard, switch to the <strong>"Dataset & Evidence"</strong> tab.<br>
        Scroll through the 14 peer-reconciled US7432034B2 electron-beam records (50 keV, 6-inch silicon wafers).<br>
        Highlight evidence snippets and standardized formulation components (P-1 resin, MM-1, CL-1, PAG).
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "High-fidelity AI requires uncompromised ground truth.<br><br>
        Our data foundation began with two independent researchers—Akhila and Kathe—who hand-annotated 10 semiconductor negative-resist patents.<br><br>
        We then deployed automated comparison techniques to audit discrepancies between the passes—resolving text-versus-table conflicts and standardized stoichiometry into a 100% consensus gold dataset of 239 records.<br><br>
        From this vetted foundation, we built and benchmarked two distinct implementation pathways: a hand-coded <strong>Manual Track</strong> and an agentic <strong>Automated Track</strong> developed by Antigravity."
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Callout Box:</strong><br>
        2 Human Annotators (Akhila & Kathe)<br>
        &rarr; Automated Discrepancy Auditing<br>
        &rarr; Reconciled 100% Consensus Gold Set<br>
        <span class="osd-badge">10 Patents &middot; 239 Records</span>
      </div>
    </div>
  </div>
</div>

<!-- PAGE 1 BREAK -->
<div class="page-break"></div>

<!-- ========================================== PAGE 2 ========================================== -->
<h2 class="section-header">Demo Video Storyboard (Part II: Automated Antigravity AI & Compliance)</h2>

<!-- Track Comparison Summary Table -->
<table class="comp-table">
  <thead>
    <tr>
      <th style="width: 20%;">Workflow Dimension</th>
      <th style="width: 40%;">Manual Track (Human Evaluation & Coding)</th>
      <th style="width: 40%;">Automated Track (Antigravity Agentic Pipeline)</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Surrogate Modeling</strong></td>
      <td>Hand-coded parametric scripts, static response bounds</td>
      <td>Dual GP with Mat&eacute;rn 5/2 kernel & LOOCV cross-validation</td>
    </tr>
    <tr>
      <td><strong>Bayesian Optimization</strong></td>
      <td>Step-by-step human inspection & manual candidate selection</td>
      <td>Autonomous Constrained Expected Improvement with dose penalty</td>
    </tr>
    <tr>
      <td><strong>PFAS Screener</strong></td>
      <td>Checklist & manual SDS chemical lookup</td>
      <td>Real-time programmatic OECD & REACH Annex XVII regex audit</td>
    </tr>
    <tr>
      <td><strong>Deployment Role</strong></td>
      <td>Exploratory sanity-checking & engineering boundary testing</td>
      <td>High-throughput autonomous formulation discovery (3&ndash;4 steps)</td>
    </tr>
  </tbody>
</table>

<!-- SCENE 3 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 3: Automated Track by Antigravity — Gaussian Process & Bayesian Optimization</span>
    <span class="scene-time">1:10 – 2:00 (50 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        Click sidebar button: <strong>"🎯 Run 1-Step Bayesian Optimization"</strong>.<br>
        Watch live recommendation update to <strong>NL-CAND-01</strong> with predicted LWR <strong>4.50 &plusmn; 0.15 nm</strong>.<br>
        Switch to <strong>"GP Surrogate Model"</strong> tab.<br>
        Point cursor to interactive <strong>Altair Response Surface</strong> with blue &plusmn;1.96&sigma; uncertainty envelope.<br>
        Highlight LOOCV metric card: <strong>MAE 1.37 nm</strong>.
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "In the Automated Track, Antigravity constructed a closed-loop Gaussian Process surrogate utilizing a Mat&eacute;rn 5/2 covariance kernel and full epistemic uncertainty quantification.<br><br>
        In rigorous Leave-One-Out Cross-Validation, the model achieves a Mean Absolute Error of just 1.37 nanometers on line roughness and 0.27 microcoulombs on dose.<br><br>
        By maximizing Expected Improvement under stepper dose constraints, the automated engine isolates the global optimum—a dual-crosslinker synergy of 65% melamine and 35% glycoluril—in just 3 to 4 iterations, cutting experimental cycles by nearly three-fold."
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Highlight Graphic:</strong><br>
        Gaussian Process (Mat&eacute;rn 5/2)<br>
        Constrained Expected Improvement (EI)<br>
        <span class="osd-badge">LOOCV MAE: 1.37 nm</span>
        <span class="osd-badge">3x Sample Efficiency</span>
      </div>
    </div>
  </div>
</div>

<!-- SCENE 4 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 4: Automated PFAS Compliance Screening & Green Substitution</span>
    <span class="scene-time">2:00 – 2:35 (35 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        Switch to <strong>"🛡️ PFAS & Regulatory Screener"</strong> tab.<br>
        Show Legacy PAG flagged in red: <em>Triphenylsulfonium nonaflate (C4F9SO3-) &rarr; OECD PFAS Banned</em>.<br>
        Show Replacement PAG in green: <em>Triphenylsulfonium Camphorsulfonate &rarr; 100% REACH / TSCA Clear</em>.<br>
        Click <strong>"Download Candidate Recipe (JSON)"</strong>.
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "Optimization is useless if a formula cannot be manufactured legally.<br><br>
        Our automated compliance agent screens candidate chemistry against OECD PFAS inventories and EU REACH SVHC restrictions.<br><br>
        When legacy perfluorononaflate is detected, the agent triggers automated stoichiometric substitution with non-fluorinated triphenylsulfonium camphorsulfonate.<br><br>
        The bulky alicyclic camphor cage limits acid diffusion during post-exposure bake, preserving 4.5-nanometer resolution with zero fluorinated effluent."
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Split Callout:</strong><br>
        Legacy: C4F9SO3- [BANNED]<br>
        Substitute: Camphorsulfonate [PASS]<br>
        <span class="osd-badge">Zero Fluorinated Effluent</span>
      </div>
    </div>
  </div>
</div>

<!-- PAGE 2 BREAK -->
<div class="page-break"></div>

<!-- ========================================== PAGE 3 ========================================== -->
<h2 class="section-header">Demo Video Storyboard (Part III: Manual Track & Outro)</h2>

<!-- SCENE 5 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 5: Manual Track — Hand-Coded Evaluation & Spin Hydrodynamics</span>
    <span class="scene-time">2:35 – 3:15 (40 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        In sidebar, toggle workflow to:<br>
        <strong>"✍️ Manual Workbench (Chemist Calculator & Rules)"</strong>.<br>
        Drag <strong>Spin Speed slider</strong> from 1000 &rarr; 1500 &rarr; 2000 RPM.<br>
        Watch live <strong>Film Thickness Metric</strong> recalculate via Meyerhofer model: <em>300 nm @ 1500 RPM</em>.<br>
        Demonstrate real-time validator checkmark: <em>✓ Passes all mass-balance and stoichiometry rules</em>.
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "To empower domain experts without relying on automated black-box loops, we developed the parallel <strong>Manual Track</strong>.<br><br>
        Here, the modeling, evaluation logic, and process calculators were hand-coded by human engineers.<br><br>
        Researchers can manually interrogate stoichiometric ratios, inspect total solids weight percent, and calculate spin-coating hydrodynamics in real time using Meyerhofer's evaporative equation—predicting exact film thickness at 1500 RPM.<br><br>
        Rule-based sanity checkers guard against improper quencher ratios or phase separation, providing complete human-in-the-loop auditability."
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Track Switcher View:</strong><br>
        Manual Modeling & Evaluation Track<br>
        Meyerhofer Film Model: $h_0 \approx 300\text{ nm}$<br>
        <span class="osd-badge">Hand-Coded Validation Logic</span>
        <span class="osd-badge">Human-in-the-Loop</span>
      </div>
    </div>
  </div>
</div>

<!-- SCENE 6 -->
<div class="scene-block">
  <div class="scene-header">
    <span>SCENE 6: Technical Report, Git Repository & Conclusion</span>
    <span class="scene-time">3:15 – 3:35 (20 sec)</span>
  </div>
  <div class="scene-body">
    <div class="scene-col">
      <div class="scene-col-title">Visual & Action</div>
      <div class="visual-action">
        Briefly display the publication PDF: <em>Negative_Lines_Technical_Report.pdf</em>.<br>
        Transition to GitHub repo: <em>github.com/whatnotalot/negative-lines</em> showing commit tree.<br>
        End on title card with live Streamlit app link and open-source license.
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">Spoken Voiceover (VO)</div>
      <div class="vo-text">
        "By uniting hand-annotated patent ground truth, manual engineering rigor, and Antigravity's autonomous AI optimization, Project Negative Lines establishes a validated blueprint for sustainable semiconductor manufacturing.<br><br>
        Explore our code, live Streamlit application, and technical paper on GitHub. Thank you!"
      </div>
    </div>
    <div class="scene-col">
      <div class="scene-col-title">On-Screen Display / Notes</div>
      <div class="osd-text">
        <strong>Final Title Screen:</strong><br>
        GitHub: whatnotalot/negative-lines<br>
        Streamlit Community Cloud Live App<br>
        <span class="osd-badge">MIT License &middot; Fully Open Source</span>
      </div>
    </div>
  </div>
</div>

<h2 class="section-header">Presenter & Video Capture Checklist</h2>

<table class="checklist-table">
  <thead>
    <tr>
      <th style="width: 25%;">Technical Element</th>
      <th style="width: 30%;">Recommended Target</th>
      <th style="width: 45%;">Presenter Note & Execution Cue</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><strong>Screen Resolution</strong></td>
      <td>1920 &times; 1080 (1080p, 16:9)</td>
      <td>Set display scaling to 100% or standard Retina; zoom browser to 110%–125% for high readability.</td>
    </tr>
    <tr>
      <td><strong>Sidebar Appearance</strong></td>
      <td>Hardcoded `#0B132B` Dark Theme</td>
      <td>Verify text contrast and radio button icons are crisp before starting capture.</td>
    </tr>
    <tr>
      <td><strong>Mouse Pacing</strong></td>
      <td>Smooth, intentional cursor paths</td>
      <td>Avoid erratic mouse waving; pause on KPI cards and Altair chart tooltips for 1.5 seconds.</td>
    </tr>
    <tr>
      <td><strong>Voiceover Pacing</strong></td>
      <td>~130–135 words per minute</td>
      <td>Leave 1-second silence before and after switching tabs to facilitate clean video editing cuts.</td>
    </tr>
    <tr>
      <td><strong>Streamlit Command</strong></td>
      <td>`streamlit run app.py`</td>
      <td>Execute from project root: `/Users/technano/agy2-projects/2026.10.OSI Hackathon/Negative Lines`.</td>
    </tr>
  </tbody>
</table>

</body>
</html>
"""

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(REPO_DOCS_DIR, exist_ok=True)

    html_path = os.path.join(OUTPUT_DIR, "Negative_Lines_Demo_Video_Script_and_Storyboard.html")
    pdf_path_1 = os.path.join(OUTPUT_DIR, PDF_NAME)
    pdf_path_2 = os.path.join(REPO_DOCS_DIR, PDF_NAME)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_CONTENT)
    print(f"✓ Wrote HTML source: {html_path}")

    # Render to PDF via Headless Chrome
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path_1}",
        html_path
    ]

    print("Rendering PDF via Google Chrome...")
    subprocess.run(cmd, check=True)
    print(f"✓ Generated PDF in movie folder: {pdf_path_1}")

    # Copy to repo docs folder
    shutil.copy2(pdf_path_1, pdf_path_2)
    print(f"✓ Mirrored PDF to repo docs: {pdf_path_2}")

if __name__ == "__main__":
    main()
