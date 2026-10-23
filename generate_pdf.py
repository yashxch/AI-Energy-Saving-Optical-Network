import sys
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (Only on page 2 and later)
        if self._pageNumber > 1:
            self.drawString(36, 762, "NOKIA NBUC PROGRAM — AI-BASED POWER SAVING IN OPTICAL NETWORKS")
            self.drawRightString(576, 762, "30-MINUTE DEMO PLAYBOOK & SCRIPT")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 754, 576, 754)
            
        # Footer
        self.setFont("Helvetica", 8)
        self.drawString(36, 25, "CONFIDENTIAL — FOR DEMO REHEARSAL & PANEL PRESENTATION ONLY")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(576, 25, page_text)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 35, 576, 35)
        
        self.restoreState()

def create_demo_script_pdf(filename):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Styles
    primary_color = colors.HexColor("#0F172A")    # Dark slate
    accent_color = colors.HexColor("#0284C7")     # Cyan / Blue
    secondary_color = colors.HexColor("#0369A1")  # Dark Cyan
    bg_light = colors.HexColor("#F8FAFC")         # Slate light
    text_dark = colors.HexColor("#1E293B")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=primary_color,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=accent_color,
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=primary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=secondary_color,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=text_dark,
        spaceAfter=6
    )

    script_say_style = ParagraphStyle(
        'ScriptSay',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=4,
        spaceAfter=6
    )

    action_style = ParagraphStyle(
        'ActionStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#047857"), # Green
        spaceBefore=2,
        spaceAfter=4
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    )

    story = []

    # Title Banner
    story.append(Paragraph("AI-BASED POWER SAVING IN OPTICAL NETWORKS", title_style))
    story.append(Paragraph("30-Minute Live Demo Playbook & Team Script — Nokia NBUC Program", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=accent_color, spaceBefore=0, spaceAfter=12))

    # Overview Box
    meta_data = [
        [Paragraph("<b>Target Event:</b> Mock Demo (Today) & Final Nokia Presentation (Tomorrow)", body_style),
         Paragraph("<b>Target Duration:</b> Exactly 28 Min Presentation + 2 Min Q&A", body_style)],
        [Paragraph("<b>Presenters:</b> Yash (Lead/AI), Chelsea (Ops/Demo), Anwesha (Twin/FCAPS)", body_style),
         Paragraph("<b>Audience:</b> Nokia Architects, Mentors & NBUC Panel Members", body_style)],
        [Paragraph("<b>Core Message:</b> <i>\"AI Recommends. Digital Twin Simulates. Policy Engine Validates. Controller Executes.\"</i>", body_style),
         Paragraph("<b>Primary Focus:</b> 80% Live Working Demo / 20% Theory", body_style)]
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # SECTION 1: MASTER TIMELINE TABLE
    story.append(Paragraph("1. MASTER 30-MINUTE TIMELINE & TEAM RESPONSIBILITIES", h1_style))
    story.append(Paragraph("The presentation strictly allocates 28 minutes for live demo and speaking, reserving the final 2 minutes exclusively for panel questions.", body_style))
    
    timeline_data = [
        ["Time Slot", "Duration", "Section Title", "Lead Speaker", "Demo Operator", "Primary Screen View"],
        ["00:00 - 02:00", "2 min", "1. Intro & Optical Power Challenge", "YASH", "CHELSEA", "Title & Architecture Slide"],
        ["02:00 - 04:00", "2 min", "2. Architecture & 4-Step Safety Flow", "YASH", "CHELSEA", "Architecture System Diagram"],
        ["04:00 - 07:00", "3 min", "3. Live Network & Telemetry Grid", "CHELSEA", "CHELSEA", "Live Telemetry & Topology View"],
        ["07:00 - 10:00", "3 min", "4. AI LSTM Traffic Prediction", "CHELSEA", "CHELSEA", "Prediction Charts (5m, 1h, 24h)"],
        ["10:00 - 12:30", "2.5 min", "5. Isolation Forest Anomaly Detection", "CHELSEA", "CHELSEA", "Anomaly Feed & Fault Injection"],
        ["12:30 - 15:00", "2.5 min", "6. LLM Reasoner & Telecom Chatbot", "YASH", "CHELSEA", "AI Telecom Assistant Chatbot"],
        ["15:00 - 18:00", "3 min", "7. Digital Twin State & Graph Model", "YASH / ANWESHA", "CHELSEA", "Digital Twin State Summary"],
        ["18:00 - 21:00", "3 min", "8. What-If Engine & Policy Validation", "ANWESHA", "CHELSEA", "What-If Comparison Panel"],
        ["21:00 - 24:00", "3 min", "9. Safe Sleep & Wake Power Execution", "ANWESHA", "CHELSEA", "Approved & Rejected Execution"],
        ["24:00 - 26:00", "2 min", "10. FCAPS Accounting & Report Export", "ANWESHA", "CHELSEA", "Energy Accounting & Report CSV/PDF"],
        ["26:00 - 28:00", "2 min", "11. Scalability, Trade-Offs & Closing", "YASH / ANWESHA", "CHELSEA", "Scalability & Roadmap Summary"],
        ["28:00 - 30:00", "2 min", "12. Reserved Panel Q&A", "ALL TEAM", "CHELSEA", "Live System Dashboard"]
    ]
    
    t_table = Table(timeline_data, colWidths=[65, 45, 175, 75, 80, 100])
    t_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), primary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light])
    ]))
    story.append(t_table)
    story.append(Spacer(1, 14))

    # SECTION 2: SECTION-BY-SECTION PLAYBOOK
    story.append(Paragraph("2. COMPLETE SECTION-BY-SECTION DEMO PLAYBOOK", h1_style))

    sections = [
        {
            "title": "SECTION 1: INTRODUCTION & OPTICAL POWER CHALLENGE",
            "time": "00:00 – 02:00", "duration": "2.0 Minutes", "speaker": "YASH", "operator": "CHELSEA",
            "screen": "Title Slide & Network Overview Dashboard",
            "objective": "Set the context: Optical transport networks consume high baseline power even during low traffic off-peak hours. Switching hardware off blindly causes QoS/SLA outages.",
            "say": "Good morning. I'm Yash, and alongside Chelsea and Anwesha, we are excited to present our project: AI-Based Power Saving in Optical Networks.\n\nIn modern optical transport architectures—like Nokia 1830 PSS—transponders, EDFAs, and ROADMs run continuously at high power mode. During off-peak hours, traffic utilization drops below 15%, yet energy consumption remains flat. \n\nWhy haven't operators automated power-saving? Because turning off an optical transponder isn't like turning off a light switch. Unsafe power reduction degrades OSNR, spikes bit-error rates, breaks 1+1 protection paths, and violates strict SLA agreements. Our objective is to automate power optimization without ever risking optical network safety.",
            "click": "1. Open dashboard at localhost:3000.\n2. Ensure header metrics show active network power (~24 kW) and total energy saved.\n3. Keep cursor ready over Network Topology.",
            "handover": "YASH: \"To solve this, we built a 4-tier closed-loop system. I'll pass to Chelsea to walk through the system architecture.\"",
            "backup": "If dashboard is loading slowly, refer to the static architecture diagram.",
            "key": "Emphasize that energy optimization MUST be optical-safety validated before execution."
        },
        {
            "title": "SECTION 2: ARCHITECTURE & THE 4-STEP SAFETY FLOW",
            "time": "02:00 – 04:00", "duration": "2.0 Minutes", "speaker": "YASH", "operator": "CHELSEA",
            "screen": "System Architecture Diagram / Topology Overview",
            "objective": "Explain the architectural principle: AI Recommends, Digital Twin Simulates, Policy Engine Validates, Controller Executes.",
            "say": "Our architecture operates on one strict operational principle:\n'AI recommends. Digital Twin simulates. Policy Engine validates. Controller executes.'\n\nFirst, real-time optical telemetry—tx/rx power, laser bias, DSP temperature, pre-FEC BER, and OSNR—is collected from 100 optical devices. Second, our LSTM traffic prediction and Isolation Forest anomaly engines analyze traffic waves. Third, when the AI identifies an energy-saving candidate, it generates a recommendation.\n\nCrucially, the AI recommendation never directly touches hardware. It is sent to our lightweight Digital Twin. The Digital Twin creates a temporary, isolated state copy, simulates the action, and passes it to a strict Policy Engine checking optical margins and protection paths. Only if approved is the command sent to the network controller.",
            "click": "1. Point cursor to the 4 workflow blocks in the view header.\n2. Highlight the boundary between AI recommendations and execution.",
            "handover": "YASH: \"Now let's see how this architecture operates live on our 100-device optical network. Chelsea will take us through the telemetry and live network.\"",
            "backup": "Explain that the core contribution is bringing Digital Twin simulation between AI recommendations and execution.",
            "key": "LLMs and ML models NEVER directly execute commands on physical hardware."
        },
        {
            "title": "SECTION 3: LIVE NETWORK TOPOLOGY & TELEMETRY GRID",
            "time": "04:00 – 07:00", "duration": "3.0 Minutes", "speaker": "CHELSEA", "operator": "CHELSEA",
            "screen": "Live Network Topology & 100 Devices Telemetry Grid",
            "objective": "Demonstrate the live network simulation across 8 core nodes and 100 real-time optical devices.",
            "say": "Thanks Yash. Here on screen is our live optical network simulation. We are actively monitoring 100 optical devices distributed across 8 major node locations: New York, Boston, Chicago, Washington DC, Atlanta, Dallas, San Francisco, and Los Angeles.\n\nOur inventory consists of 50 800G Transponders, 20 EDFA Optical Amplifiers, 15 ROADM WSS units, and 15 Filter Cards. \n\nNotice the live Telemetry Grid below. Every 1 second, our telemetry engine streams 17 parameters per device—including DSP core temperature, laser bias current, pre-FEC BER, post-FEC BER, Q-factor in dB, and OSNR. Notice TRX-800G-005 located in New York: it's operating in Normal mode drawing 350 Watts, but its traffic utilization is currently at only 14%. This low utilization makes it an ideal candidate for power optimization.",
            "click": "1. Click 'NYC' node on visual topology to filter NYC devices.\n2. Scroll down to Telemetry Grid.\n3. Click TRX-800G-005 card to expand telemetry parameters (Traffic: 14%, Power: 350W, OSNR: 26.5 dB, Pre-FEC BER: 1.2e-9).\n4. Point out the live updating timestamp.",
            "handover": "CHELSEA: \"Collecting telemetry is step one. Step two is predicting traffic trends so we don't sleep devices right before a surge. Let's look at the AI Traffic Prediction engine.\"",
            "backup": "If live streaming stalls, click 'Refresh Telemetry' in top right.",
            "key": "Show real telemetry parameters (OSNR, Pre-FEC BER, DSP temp, Power W) on 800G transponders."
        },
        {
            "title": "SECTION 4: AI/ML TRAFFIC PREDICTION ENGINE",
            "time": "07:00 – 10:00", "duration": "3.0 Minutes", "speaker": "CHELSEA", "operator": "CHELSEA",
            "screen": "Traffic Prediction Charts (5m, 1h, 24h Horizons)",
            "objective": "Demonstrate LSTM diurnal traffic modeling and multi-horizon prediction.",
            "say": "Here we see our Machine Learning Traffic Prediction engine. Optical network traffic follows a diurnal wave pattern—peaking during business hours and dropping sharply at night. \n\nWe trained an LSTM neural network model to predict aggregate network demand across three time horizons: 5 minutes, 1 hour, and 24 hours. On the chart, the solid cyan line shows our predicted traffic in Gbps, while the upper and lower shaded regions represent our 95% confidence intervals.\n\nRight now, for the upcoming 1-hour horizon, the LSTM model predicts traffic will remain under 18% of capacity on the NYC-BOS span. This high-confidence low-traffic forecast gives our system the green light to evaluate transponder sleep mode without fearing immediate packet drops.",
            "click": "1. Switch tabs between '5m', '1h', and '24h' prediction horizons.\n2. Hover cursor over prediction data points to reveal upper/lower bound tooltips.\n3. Highlight confidence score (96% for 5m, 91% for 1h).",
            "handover": "CHELSEA: \"Alongside prediction, we must continuously monitor network health for optical anomalies. I'll show how our Isolation Forest model detects fault conditions.\"",
            "backup": "Explain that harmonic LSTM modeling tracks diurnal waves accurately.",
            "key": "ML predictions provide confidence boundaries so sleep mode isn't triggered before traffic spikes."
        },
        {
            "title": "SECTION 5: ISOLATION FOREST ANOMALY DETECTION",
            "time": "10:00 – 12:30", "duration": "2.5 Minutes", "speaker": "CHELSEA", "operator": "CHELSEA",
            "screen": "Anomaly Detection Feed & Live Fault Injector",
            "objective": "Demonstrate real-time anomaly detection and policy blocking during hardware degradation.",
            "say": "To ensure safety, our system runs an unsupervised Isolation Forest model alongside heuristic threshold boundaries across all 100 devices. The model evaluates four-dimensional feature vectors: DSP temperature, log Pre-FEC BER, OSNR, and power draw.\n\nLet's test this live. I will inject a simulated 'BER Spike' fault into Transponder TRX-800G-003.\n\nNotice how the anomaly feed immediately flags TRX-800G-003 with a Warning severity and high anomaly score. Pre-FEC BER degraded to 8.5e-4. Most importantly, the system automatically blocks all AI power-saving actions on this device. When optical signal quality is compromised, power optimization is prohibited.",
            "click": "1. Scroll to Demo Fault Simulator in top header.\n2. Select device 'TRX-800G-003' and fault 'BER_SPIKE'.\n3. Click 'Inject' button.\n4. Show anomaly banner appearing in Red/Yellow under Anomaly Detection Feed.\n5. Click 'Clear' button to restore nominal operation.",
            "handover": "CHELSEA: \"Now that we've seen how ML predicts traffic and flags anomalies, Yash will explain how our LLM engine converts telemetry into actionable recommendations.\"",
            "backup": "If fault injection takes a second, point to existing telemetry threshold flags.",
            "key": "Anomalies automatically block power-saving state changes on degraded channels."
        },
        {
            "title": "SECTION 6: LLM TELECOM REASONER & CHATBOT",
            "time": "12:30 – 15:00", "duration": "2.5 Minutes", "speaker": "YASH", "operator": "CHELSEA",
            "screen": "AI Telecom Assistant Floating Chatbot & Recommendation Cards",
            "objective": "Demonstrate LLM natural language explainability and operator support without direct hardware execution.",
            "say": "Thanks Chelsea. In telecom operations, NOC engineers need natural language explainability—not black-box decisions. This is where our LLM Reasoning engine fits in.\n\nThe LLM receives structured telemetry, LSTM predictions, and policy checks, and generates natural language explanations. Let's ask our AI Optical Assistant: 'Why is Transponder TRX-800G-003 consuming power?'\n\nThe LLM responds instantly with real telemetry context: current power draw is 350W, traffic is 14%, and DSP temperature is nominal. It explains that TRX-003 is operating in 800G PAM4 modulation mode and recommends evaluating sleep mode.\n\nWe emphasize again: the LLM is an explanation layer. It recommends; it does NOT execute commands directly on the hardware.",
            "click": "1. Click floating Chatbot icon in bottom-right corner.\n2. Type prompt: 'Why is Transponder TRX-800G-003 consuming power?' or click preset prompt button.\n3. Show generated markdown response with live telemetry values.\n4. Close chatbot window.",
            "handover": "YASH: \"Now comes the core innovation of our project: passing this recommendation to the Digital Twin. Anwesha will demonstrate our Digital Twin and What-If engine.\"",
            "backup": "If chatbot API delay occurs, read recommendation reasoning card from Power Optimization panel.",
            "key": "LLM serves as human-readable reasoning and NOC assistant, NOT hardware controller."
        },
        {
            "title": "SECTION 7: DIGITAL TWIN STATE MODEL & GRAPH TOPOLOGY",
            "time": "15:00 – 18:00", "duration": "3.0 Minutes", "speaker": "YASH / ANWESHA", "operator": "CHELSEA",
            "screen": "Digital Twin State Summary & NetworkX Topology Graph",
            "objective": "Explain the lightweight Digital Twin state representation and zero-overhead synchronization.",
            "say": "ANWESHA: Thank you Yash. We are now looking at our dedicated Digital Twin & What-If Engine Dashboard.\n\nA critical requirement from optical network architects is resource efficiency. Our Digital Twin is NOT a second physical network, nor does it run a second heavy network simulator. Instead, it is a lightweight, centralized state representation synchronized directly from existing telemetry every 1 second.\n\nOn screen, you see our NetworkX-backed Graph Topology model. Nodes represent network hubs, while edges represent optical links with link capacity, available bandwidth, optical distance in kilometers, and 1+1 protection relationships. Notice the sync badge in the top right: it displays SYNCED in green, showing that all 100 devices are synchronized with zero telemetry lag.",
            "click": "1. Click '🌐 Digital Twin & What-If Engine' tab in main navigation.\n2. Point out Digital Twin Summary Header: Total Devices 100, Active 90, Sleeping 10, Sync Badge 'SYNCED'.\n3. Hover over Graph Topology node boxes (NYC, BOS, CHI) showing active transponders & link utilization.",
            "handover": "ANWESHA: \"Now let's see what happens when the AI recommends sleeping a transponder. I'll walk through our What-If simulation engine.\"",
            "backup": "Highlight that NetworkX in Python provides instant graph evaluation without memory leaks.",
            "key": "Digital Twin is lightweight, event-synchronized, and consumes zero duplicate simulator resources."
        },
        {
            "title": "SECTION 8: WHAT-IF SIMULATION & POLICY VALIDATION",
            "time": "18:00 – 21:00", "duration": "3.0 Minutes", "speaker": "ANWESHA", "operator": "CHELSEA",
            "screen": "What-If Simulation Panel (Approved vs Rejected Scenarios)",
            "objective": "Demonstrate on-demand What-If simulation on temporary cloned state and policy validation.",
            "say": "When an AI recommendation arrives—for example, 'Put Transponder TRX-800G-005 into sleep mode'—our What-If Engine creates a temporary, isolated clone of the current twin state. It simulates state change, re-routes traffic across available graph links, and evaluates 5 strict optical policies:\n\n1. QoS Guarantee: Traffic load must be below 20%.\n2. OSNR Optical Margin: Projected OSNR must remain above 14.5 dB.\n3. Pre-FEC BER: Must remain below 1.0e-4.\n4. Link Budget Safety Buffer: Margin must be >= 2.5 dB.\n5. SLA 1+1 Protection Path: Redundant path must exist and remain below 85% capacity.\n\nLet's test Scenario 1. TRX-800G-005 has 12% traffic, OSNR of 26.5 dB, and valid protection. As you can see, all 5 policy checks pass! The validation status reads APPROVED in green, and the temporary simulation state is immediately discarded.",
            "click": "1. Scroll to Interactive What-If Simulation Panel.\n2. Click 'Scenario 1: Low Traffic Transponder Sleep (Approved)' demo button.\n3. Point out side-by-side table: Power 350W ➔ 45W, Traffic 12% ➔ 0%, OSNR 26.5 dB ➔ 25.5 dB.\n4. Show 5 green checkmarks under Policy Validation Checklist.\n5. Highlight APPROVED badge.",
            "handover": "ANWESHA: \"Approval is great, but what happens when an AI recommendation is UNSAFE? Let's demonstrate Scenario 2.\"",
            "backup": "If button click is delayed, manually select TRX-800G-005 and click 'Run What-If Simulation'.",
            "key": "Temporary What-If simulation state is cloned, evaluated against 5 optical policies, and discarded."
        },
        {
            "title": "SECTION 9: SAFE SLEEP & WAKE POWER OPTIMIZATION",
            "time": "21:00 – 24:00", "duration": "3.0 Minutes", "speaker": "ANWESHA", "operator": "CHELSEA",
            "screen": "What-If Panel (Scenario 2 Rejected & Scenario 3 Wake-Up)",
            "objective": "Demonstrate rejection of unsafe recommendations (degraded OSNR / protection failure) and proactive wake-up.",
            "say": "This is the most important moment of our demo. In Scenario 2, Transponder TRX-800G-012 reports low traffic (14%), but its OSNR is degraded to 13.8 dB—violating our 14.5 dB safety threshold. \n\nThe AI proposes sleep, but our Digital Twin simulates the link drop and the Policy Engine immediately flags REJECTED in red. Unsafe actions can NEVER bypass our policy engine.\n\nNow look at Scenario 3: Proactive Wake-Up. Traffic on the NYC ingress span surges to 82%. The Digital Twin detects predicted congestion, simulates waking sleeping Transponder TRX-800G-018 from 45W back to 350W, validates that capacity increases by 800 Gbps, and approves the WAKE command! We then click 'Execute' to apply the change directly to the network controller.",
            "click": "1. Click 'Scenario 2: Low Traffic but Degraded OSNR (Rejected)' button.\n2. Highlight RED REJECTED banner and failed OSNR check (13.8 dB < 14.5 dB limit).\n3. Click 'Scenario 3: Traffic Spike Proactive Wake-Up (Approved)' button.\n4. Show GREEN APPROVED banner for WAKE action.\n5. Click '🚀 Execute Approved Action on Network' button.\n6. Point to success message: 'Digital Twin applied WAKE to TRX-800G-018'.",
            "handover": "ANWESHA: \"Once safe optimizations execute, we track accumulated energy accounting and report generation. Let's review our FCAPS reporting capabilities.\"",
            "backup": "Emphasize: 'Safety first—an unsafe AI recommendation is blocked 100% of the time.'",
            "key": "Rejection of unsafe AI recommendations proves the Digital Twin safety boundary works."
        },
        {
            "title": "SECTION 10: FCAPS ENERGY ACCOUNTING & REPORT EXPORT",
            "time": "24:00 – 26:00", "duration": "2.0 Minutes", "speaker": "ANWESHA", "operator": "CHELSEA",
            "screen": "FCAPS Dashboard — Energy Accounting & Report Generation",
            "objective": "Demonstrate FCAPS energy accounting, OPEX cost savings, CO2 reduction, and CSV/PDF export.",
            "say": "Now let's examine our FCAPS Accounting and Reporting layer. As transponders enter sleep mode and amplifiers operate in eco mode, our accounting engine tracks cumulative savings.\n\nCurrently, our network baseline power is 125.0 kW. With AI power optimization active, active draw drops to 97.0 kW—achieving a 22.4% power reduction. Accumulated energy savings total 142.5 kWh, translating to $19.95 in OPEX cost savings and 59.8 kg of CO2 emissions avoided.\n\nFor telecom auditing, operators can click 'Generate Executive Energy Report' to export full telemetry, anomaly history, Digital Twin simulation audit logs, and policy decision records directly into printable PDF or CSV format.",
            "click": "1. Scroll down to FCAPS Energy Accounting section.\n2. Point to 24-Hour Historical Power Curve chart (Baseline kW vs AI Optimized kW).\n3. Click 'Generate Executive Energy Report' button.\n4. Show report modal previewing summary table and CSV download button.",
            "handover": "ANWESHA: \"Finally, Yash and I will summarize our system scalability, current prototype limitations, and key takeaways.\"",
            "backup": "Show the live energy savings counter updating in the top header bar.",
            "key": "Quantify real savings: 22.4% power reduction, 142.5 kWh saved, PDF/CSV export ready."
        },
        {
            "title": "SECTION 11: SCALABILITY, LIMITATIONS & FINAL TAKEAWAY",
            "time": "26:00 – 28:00", "duration": "2.0 Minutes", "speaker": "YASH / ANWESHA", "operator": "CHELSEA",
            "screen": "Scalability Summary & System Health Dashboard",
            "objective": "Summarize scalability from 100 to 10,000 devices, acknowledge prototype scope, and deliver closing takeaway.",
            "say": "YASH: To scale from 100 devices to 10,000 devices in production, our architecture relies on event-driven state delta updates and on-demand simulation. Because Digital Twin simulation state is cloned on-demand and discarded immediately, memory utilization remains flat under 120 MB regardless of network size.\n\nANWESHA: We also maintain complete engineering honesty regarding current limitations. This project is a software prototype simulating Nokia 1830 PSS telemetry rather than connected to live physical EDFA hardware. Moving to production requires integrating Nokia NETCONF/YANG APIs and RESTCONF transport interfaces.\n\nYASH: In conclusion, our system proves that AI-driven power saving in optical networks can be achieved safely: 'AI recommends, Digital Twin simulates, Policy Engine validates, Controller executes.' Thank you. We are now open for your questions.",
            "click": "1. Scroll to top of main dashboard overviewing live system.\n2. Keep screen open on live dashboard for panel Q&A.",
            "handover": "YASH: \"Thank you. We are ready for Q&A.\"",
            "backup": "Keep live dashboard open behind Q&A so panel can request specific device views.",
            "key": "Finish presentation exactly at 28:00, leaving full 2 minutes for panel questions."
        },
        {
            "title": "SECTION 12: RESERVED PANEL QUESTIONS & ANSWERS",
            "time": "28:00 – 30:00", "duration": "2.0 Minutes", "speaker": "ALL TEAM", "operator": "CHELSEA",
            "screen": "Live System Dashboard (Ready for Panel Inquiries)",
            "objective": "Answer panel questions concisely (20-45 seconds per response) using implemented project architecture.",
            "say": "TEAM: We welcome any questions from the panel.",
            "click": "1. Be ready to click any device, run a what-if simulation, or open policies.json if requested by panel.",
            "handover": "None (Interactive Q&A Session).",
            "backup": "Refer to Section 3 and Section 4 of this playbook for detailed Q&A answers.",
            "key": "Answer concisely in 20-45 seconds. Cross-reference specific codebase components."
        }
    ]

    for s in sections:
        sec_elements = []
        sec_elements.append(Paragraph(f"{s['title']} ({s['time']})", h2_style))
        
        sec_table_data = [
            [Paragraph(f"<b>Time Slot:</b> {s['time']}", body_style), Paragraph(f"<b>Duration:</b> {s['duration']}", body_style)],
            [Paragraph(f"<b>Lead Speaker:</b> {s['speaker']}", body_style), Paragraph(f"<b>Demo Operator:</b> {s['operator']}", body_style)],
            [Paragraph(f"<b>Screen View:</b> {s['screen']}", body_style), Paragraph(f"<b>Objective:</b> {s['objective']}", body_style)]
        ]
        sec_table = Table(sec_table_data, colWidths=[270, 270])
        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_light),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        sec_elements.append(sec_table)
        sec_elements.append(Spacer(1, 6))

        # Speaking Script Box
        sec_elements.append(Paragraph("<b>WHAT TO SAY (NATURAL SCRIPT):</b>", ParagraphStyle('SubHeader', parent=body_style, fontName='Helvetica-Bold', textColor=accent_color)))
        say_paragraphs = s['say'].split('\n\n')
        for p in say_paragraphs:
            sec_elements.append(Paragraph(f"\"{p}\"", script_say_style))

        # Demo Action Box
        sec_elements.append(Spacer(1, 4))
        sec_elements.append(Paragraph("<b>WHAT CHELSEA CLICKS & SHOWS:</b>", ParagraphStyle('SubHeader2', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor("#047857"))))
        click_lines = s['click'].split('\n')
        for cl in click_lines:
            sec_elements.append(Paragraph(cl, action_style))

        # Handover & Callouts
        sec_elements.append(Spacer(1, 4))
        h_table_data = [
            [Paragraph(f"<b>HANDOVER:</b> {s['handover']}", body_style)],
            [Paragraph(f"<b>BACKUP PLAN:</b> {s['backup']}", body_style)],
            [Paragraph(f"<b>KEY POINT TO EMPHASIZE:</b> {s['key']}", ParagraphStyle('KP', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor("#B91C1C")))]
        ]
        h_table = Table(h_table_data, colWidths=[540])
        h_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#FCA5A5")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#FEE2E2")),
            ('PADDING', (0,0), (-1,-1), 4),
        ]))
        sec_elements.append(h_table)
        sec_elements.append(Spacer(1, 12))
        
        story.append(KeepTogether(sec_elements))

    # SECTION 3: LIKELY NOKIA PANEL QUESTIONS & ANSWERS (22 QUESTIONS)
    story.append(PageBreak())
    story.append(Paragraph("3. LIKELY NOKIA PANEL QUESTIONS & ANSWERS (22 QUESTIONS)", h1_style))
    story.append(Paragraph("Concise, technically sound responses prepared for panel inquiry (20–45 seconds each).", body_style))

    panel_qa = [
        ("1. Why do you need AI if FCAPS already exists?",
         "FCAPS handles static threshold monitoring and reactive alarms. AI provides proactive demand prediction via LSTM models and multi-variable pattern recognition (BER, OSNR, temperature) that static FCAPS rules cannot anticipate."),

        ("2. What exactly does the LLM contribute?",
         "The LLM acts as a natural language reasoning and NOC operator assistant layer. It translates complex multi-variable telemetry and policy checks into plain-English explainability. It does NOT control hardware."),

        ("3. Why can't the LLM directly control the hardware?",
         "LLMs are probabilistic and prone to hallucination. Telecom optical infrastructure requires deterministic safety guarantees. Hardware control is strictly reserved for our deterministic Policy Engine and network controller."),

        ("4. How does the Digital Twin prevent unsafe decisions?",
         "The Digital Twin creates an isolated What-If state clone, simulates traffic redistribution across graph links, and tests 5 optical constraints (QoS, OSNR >= 14.5dB, BER <= 1e-4, link budget >= 2.5dB, 1+1 protection capacity). If any fail, execution is blocked."),

        ("5. How do you validate OSNR?",
         "We model projected OSNR deltas based on channel power adjustments (-1.0 dB for transponder sleep, -2.5 dB for amplifier gain reduction) and compare against the receiver threshold of 14.5 dB."),

        ("6. How do you handle protection paths?",
         "During What-If simulation, we model traffic offloading onto secondary 1+1 Optical Subnetwork Connection (OSC) protection paths. If protection path utilization exceeds 85% or backup path is unassigned, sleep mode is rejected."),

        ("7. What happens if telemetry is stale?",
         "If telemetry age exceeds 5.0 seconds (configured in policies.json), the Digital Twin flags state as STALE and triggers fail-safe behavior: automatic validation is BLOCKED and REQUIRES_OPERATOR_APPROVAL is returned."),

        ("8. How do you decide when a device enters sleep mode?",
         "A transponder enters sleep mode only when: traffic < 20%, predicted demand remains low, OSNR >= 14.5 dB, Pre-FEC BER <= 1e-4, link margin >= 2.5 dB, 1+1 protection path is available (< 85% load), and no critical alarms exist."),

        ("9. How do you decide when it wakes up?",
         "Proactive wake-up is triggered when active link traffic exceeds 70% or LSTM predicts future congestion > 80%. The Digital Twin simulates waking a sleeping unit, verifies 800G capacity addition, and executes WAKE."),

        ("10. What happens if traffic suddenly increases?",
         "If an unpredicted traffic spike occurs, our 1-second telemetry loop detects utilization crossing threshold limits and immediately initiates transponder wake-up or traffic rerouting before packet drop occurs."),

        ("11. How do you avoid affecting QoS?",
         "QoS is protected by enforcing strict capacity headroom limits (max 20% load for sleep), validating 1+1 protection paths, and continuously monitoring Pre-FEC BER. Unsafe sleep actions are rejected 100% of the time."),

        ("12. How does the system scale?",
         "The Digital Twin uses event-driven state delta updates and on-demand What-If cloning. Memory isolation ensures temporary simulation copies are discarded immediately, keeping RAM footprint under 120 MB even for 10,000 devices."),

        ("13. How do you prevent false AI recommendations?",
         "All AI recommendations must pass deterministic Policy Engine validation on cloned Digital Twin states. AI recommendations that fail optical margins are flagged REJECTED and discarded."),

        ("14. Why use a Digital Twin instead of simply using a simulator?",
         "A simulator generates synthetic telemetry. A Digital Twin maintains a synchronized, stateful virtual replica of the live network topology, allowing non-destructive What-If evaluation of real operational impacts."),

        ("15. How do you avoid doubling resource usage with the Digital Twin?",
         "Our Digital Twin shares the existing telemetry stream and NetworkX graph model. It does NOT run a second physical network or duplicate database. What-If states are temporary clones freed immediately after check."),

        ("16. How would this integrate with Nokia 1830 PSS?",
         "In production, our telemetry ingest module connects to Nokia 1830 PSS NETCONF/YANG telemetry interfaces (gNMI/RESTCONF), while our controller module issues YANG RPC power state mutations to Nokia NFM-P/NSP controllers."),

        ("17. How would FCAPS integrate with the system?",
         "FCAPS provides foundational fault event generation and energy accounting logs. Our Digital Twin feeds validated execution events back into FCAPS Security and Energy Accounting logs for operator compliance auditing."),

        ("18. How would you collect telemetry from real Nokia hardware?",
         "Using streaming telemetry over gRPC (gNMI) or RESTCONF telemetry subscriptions from Nokia 1830 PSS transponders and EDFAs, streaming JSON telemetry directly into our sync engine."),

        ("19. What happens if the AI recommendation is wrong?",
         "The Policy Engine acts as an air-gapped firewall. If an AI recommendation is wrong (e.g. recommending sleep during high traffic or poor OSNR), the Policy Engine rejects it with a specific optical policy failure reason."),

        ("20. What is the difference between prediction, recommendation and execution?",
         "Prediction forecasts future traffic demand (LSTM). Recommendation identifies potential energy savings (LLM/ML). Execution applies validated state changes to hardware controllers after Digital Twin policy approval."),

        ("21. What are the current limitations?",
         "This is a software prototype simulating Nokia 1830 PSS telemetry rather than connected to physical optical hardware. Optical margin deltas are modeled rather than computed via full wave-equation solvers."),

        ("22. What would be required to move this from prototype to production?",
         "1) Connecting gNMI streaming telemetry from physical Nokia 1830 PSS shelves. 2) Integrating Nokia NSP RESTCONF APIs for YANG RPC execution. 3) Field testing policy thresholds in a testbed.")
    ]

    for q, a in panel_qa:
        qa_element = [
            Paragraph(f"<b>{q}</b>", ParagraphStyle('QStyle', parent=body_style, fontName='Helvetica-Bold', textColor=accent_color)),
            Paragraph(f"<b>Answer:</b> {a}", ParagraphStyle('AStyle', parent=body_style, fontName='Helvetica', textColor=text_dark)),
            Spacer(1, 4)
        ]
        story.append(KeepTogether(qa_element))

    # SECTION 4: DIFFICULT ARCHITECT-LEVEL QUESTIONS (15 QUESTIONS)
    story.append(PageBreak())
    story.append(Paragraph("4. DIFFICULT ARCHITECT-LEVEL QUESTIONS & ANSWERS (15 QUESTIONS)", h1_style))
    story.append(Paragraph("Deep technical responses designed for Nokia Principal Architects and System Engineers.", body_style))

    arch_qa = [
        ("1. How do you prove that an AI-generated optimization is safe?",
         "Safety is mathematically proven by deterministic boolean assertion over 5 bounded inequalities: Traffic <= 20%, OSNR >= 14.5dB, Pre-FEC BER <= 1e-4, Link Margin >= 2.5dB, and Protection Path Load <= 85%. AI never bypasses these assertions."),

        ("2. What is your fail-safe mechanism?",
         "If telemetry is stale (>5s delay), telemetry fields are missing, protection paths are unassigned, or an active critical alarm exists, the Policy Engine defaults to REJECTED or REQUIRES_OPERATOR_APPROVAL and locks current hardware power states."),

        ("3. What happens when telemetry sources disagree?",
         "We enforce conservative worst-case bounds. If transponder rx_power and downstream EDFA ingress power disagree, the lower OSNR and higher BER reading is selected for policy validation."),

        ("4. How do you handle conflicting optimization objectives (e.g. Power vs Latency)?",
         "Resilience and QoS take strict priority over power savings. Power optimization is only considered when network state lies strictly inside the safe operating envelope."),

        ("5. How do you trade off energy savings against network resilience?",
         "1+1 protection path availability is a non-negotiable hard constraint. A transponder will never be placed in sleep mode if it reduces protection route capacity below required SLA thresholds."),

        ("6. What happens during protection switching?",
         "During a protection switch event, FCAPS flags a major fault alarm, suspending all power optimization routines network-wide until topology graph connectivity stabilizes."),

        ("7. How would your system behave during a sudden fiber cut?",
         "A fiber cut triggers instant loss-of-signal alarms. Our Digital Twin topology graph updates edge availability to inactive, and sleeping transponders on backup routes are immediately woken up to absorb rerouted traffic."),

        ("8. How would you prevent oscillation between sleep and wake states?",
         "We implement a hysteresis timer (minimum 300 seconds in sleep state before re-evaluating) and enforce a 15% delta margin between sleep entry threshold (20%) and wake trigger threshold (35%)."),

        ("9. How do you handle prediction uncertainty?",
         "Our LSTM traffic predictor generates 95% confidence bounds. Policy validation evaluates the upper confidence bound rather than mean predicted traffic to guarantee headroom."),

        ("10. What happens if the Digital Twin state becomes stale?",
         "State freshness is tracked per device. If last_updated exceeds policies.json timeout (5.0s), sync status changes to STALE and all What-If simulation approvals are blocked until telemetry sync resumes."),

        ("11. How would you validate the Digital Twin against the real network?",
         "By performing periodic state reconciliation: comparing Digital Twin graph parameters against Nokia NSP active topology state models and verifying 0-delta parameter alignment."),

        ("12. How would you measure the effectiveness of the optimization?",
         "By calculating active power draw reduction against our fixed baseline (125 kW baseline minus live kW draw) and tracking accumulated kWh, OPEX cost savings ($0.14/kWh), and CO2 offset (0.42 kg/kWh)."),

        ("13. What happens if the optimal energy-saving decision conflicts with an SLA?",
         "SLA compliance is encoded as a hard constraint in policy_engine.py. If an energy-saving decision violates SLA protection path availability, it is rejected regardless of power savings."),

        ("14. How would you handle thousands of optical devices?",
         "Using distributed state synchronization with NetworkX graph partitioning. Telemetry ingestion is decoupled from on-demand simulation, ensuring O(1) memory complexity per What-If evaluation."),

        ("15. Why should an operator trust an LLM recommendation?",
         "Operators do not trust the LLM blindly. The LLM provides plain-English explainability, but actual execution requires deterministic validation by the Policy Engine on temporary Digital Twin state copies.")
    ]

    for q, a in arch_qa:
        qa_element = [
            Paragraph(f"<b>{q}</b>", ParagraphStyle('QStyle2', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor("#0369A1"))),
            Paragraph(f"<b>Deep Technical Answer:</b> {a}", ParagraphStyle('AStyle2', parent=body_style, fontName='Helvetica', textColor=text_dark)),
            Spacer(1, 4)
        ]
        story.append(KeepTogether(qa_element))

    # SECTION 5: HANDOVER SCRIPT & BACKUP TROUBLESHOOTING MATRIX
    story.append(PageBreak())
    story.append(Paragraph("5. TEAM HANDOVER SCRIPT & BACKUP TROUBLESHOOTING MATRIX", h1_style))

    story.append(Paragraph("<b>EXACT TEAM HANDOVER TRANSITIONS:</b>", ParagraphStyle('SubH3', parent=body_style, fontName='Helvetica-Bold', textColor=accent_color)))
    
    handovers = [
        ("YASH ➔ CHELSEA (At 04:00)",
         "YASH: \"Now that we've seen how the 4-step safety architecture is structured, Chelsea will show us how this is reflected live in our optical network.\"\nCHELSEA: \"Thanks Yash. I'll start by walking through our live topology and 100-device telemetry grid.\""),
        
        ("CHELSEA ➔ YASH (At 12:30)",
         "CHELSEA: \"Now that we've seen how ML predicts traffic and flags anomalies, Yash will explain how our LLM engine converts telemetry into actionable recommendations.\"\nYASH: \"Thanks Chelsea. In telecom operations, NOC engineers need explainability—not black-box decisions.\""),
        
        ("YASH ➔ ANWESHA (At 15:00)",
         "YASH: \"Now comes the core innovation of our project: passing recommendations to the Digital Twin. Anwesha will demonstrate our Digital Twin and What-If engine.\"\nANWESHA: \"Thank you Yash. We are now looking at our dedicated Digital Twin & What-If Engine Dashboard.\""),
        
        ("ANWESHA ➔ YASH / CLOSING (At 26:00)",
         "ANWESHA: \"Finally, Yash and I will summarize our system scalability, prototype scope, and key takeaways.\"\nYASH: \"In conclusion, our system proves that AI-driven power saving in optical networks can be achieved safely: AI recommends, Digital Twin simulates, Policy Engine validates, Controller executes. Thank you. We are open for questions.\"")
    ]

    for title, h_text in handovers:
        h_box = [
            Paragraph(f"<b>{title}</b>", ParagraphStyle('HTitle', parent=body_style, fontName='Helvetica-Bold', textColor=primary_color)),
            Paragraph(h_text.replace('\n', '<br/>'), script_say_style),
            Spacer(1, 4)
        ]
        story.append(KeepTogether(h_box))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>BACKUP TROUBLESHOOTING MATRIX (IF SOMETHING FAILS LIVE):</b>", ParagraphStyle('SubH4', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor("#B91C1C"))))

    trouble_data = [
        ["Failure Scenario", "Operator Action (Chelsea)", "Speaker Transition / Recovery Statement"],
        ["Backend API Unavailable", "Restart `uvicorn app.main:app --reload` or refresh page.", "YASH: \"While the API reconnects, let me explain our 5 policy assertions...\""],
        ["Frontend UI Freezes", "Press F5 or Ctrl+R to hard refresh localhost:3000.", "CHELSEA: \"Refreshing the view. As you can see, telemetry polling resumes immediately...\""],
        ["LLM Chatbot Timeout", "Click preset chatbot prompt button or read reasoning card.", "YASH: \"The structured telemetry reasoning card displays the exact policy checks...\""],
        ["Demo Scenario Button Stalls", "Manually select device in dropdown and click 'Run Simulation'.", "ANWESHA: \"We can also select any of the 100 devices manually to simulate What-If state...\""],
        ["Fault Injector Delayed", "Point to active telemetry threshold warning flags in grid.", "CHELSEA: \"Notice that threshold boundary checks continuously flag degraded channels...\""]
    ]

    tr_table = Table(trouble_data, colWidths=[120, 180, 240])
    tr_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#991B1B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#FCA5A5")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FEF2F2")])
    ]))
    story.append(tr_table)

    # SECTION 6: CHECKLISTS & REHEARSAL PLAN
    story.append(PageBreak())
    story.append(Paragraph("6. MOCK/FINAL CHECKLISTS & REHEARSAL PLAN", h1_style))

    story.append(Paragraph("<b>MOCK DEMO CHECKLIST (TODAY) & FINAL DEMO CHECKLIST (TOMORROW):</b>", h2_style))

    checklists = [
        ("MOCK DEMO CHECKLIST (TODAY)", [
            "[ ] Backend FastAPI server running on http://localhost:8000",
            "[ ] Frontend Next.js app running on http://localhost:3000",
            "[ ] Verify 100 optical devices telemetry streaming in Telemetry Grid",
            "[ ] Verify 5m, 1h, 24h prediction charts loading in PredictionCharts component",
            "[ ] Verify Isolation Forest anomaly feed and fault injector (BER_SPIKE, OVERHEAT)",
            "[ ] Verify AI Telecom Chatbot responding to query 'Why is Transponder 3 consuming power?'",
            "[ ] Verify Digital Twin tab sync status badge displays SYNCED in green",
            "[ ] Test What-If Simulation Scenario 1 (Approved Sleep) and Scenario 2 (Rejected OSNR)",
            "[ ] Test Action Execution ('🚀 Execute Approved Action on Network')",
            "[ ] Verify FCAPS Energy Accounting chart and 'Generate Executive Energy Report' PDF/CSV export"
        ]),
        ("FINAL NOKIA DEMO CHECKLIST (TOMORROW)", [
            "[ ] Launch backend & frontend 30 minutes before presentation session",
            "[ ] Confirm microphone and screen sharing permissions in video call software",
            "[ ] Open localhost:3000 in browser, set zoom to 90% for clean widescreen presentation",
            "[ ] Close all unnecessary browser tabs, messaging apps, and system notifications",
            "[ ] Run `python test_backend.py` to confirm zero backend errors before going live",
            "[ ] Keep PDF Demo Playbook open on second screen or printed beside presenters",
            "[ ] Confirm timer is set for exactly 28 minutes presentation / 2 minutes Q&A",
            "[ ] Ensure Chelsea, Yash, and Anwesha have agreed on handover transition cues"
        ])
    ]

    for title, items in checklists:
        chk_box = [
            Paragraph(f"<b>{title}</b>", ParagraphStyle('CTitle', parent=body_style, fontName='Helvetica-Bold', textColor=primary_color)),
        ]
        for it in items:
            chk_box.append(Paragraph(it, body_style))
        chk_box.append(Spacer(1, 4))
        story.append(KeepTogether(chk_box))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>5-ROUND TEAM REHEARSAL PLAN:</b>", h2_style))

    rehearsal_data = [
        ["Round", "Focus Area", "Target Goal"],
        ["ROUND 1", "Script Read-Through", "Align on exact technical terms and handover transitions."],
        ["ROUND 2", "Unscripted Demo Execution", "Perform live UI clicks while speaking naturally without looking at script."],
        ["ROUND 3", "Timed 28-Minute Dry Run", "Strictly enforce 28-minute timer. Adjust speaking speed to fit window."],
        ["ROUND 4", "Simulated Technical Interruptions", "Practice responding when panel interrupts with questions mid-demo."],
        ["ROUND 5", "Fault & Recovery Simulation", "Test backup recovery plan (UI refresh, manual scenario selection)."]
    ]

    r_table = Table(rehearsal_data, colWidths=[70, 180, 290])
    r_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), secondary_color),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light])
    ]))
    story.append(r_table)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully generated: {filename}")

if __name__ == "__main__":
    out_pdf = os.path.abspath("AI_Power_Saving_Nokia_30_Minute_Demo_Script.pdf")
    create_demo_script_pdf(out_pdf)
