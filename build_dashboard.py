#!/usr/bin/env python3
"""
build_dashboard.py
Reads ticket JSON from stdin or file arg, rebuilds index.html sections.
Usage: python3 build_dashboard.py /path/to/tickets.json /path/to/index.html
"""
import sys, json, re, html as htmlmod
from datetime import date, timedelta

STAGES = {
    '1053718669': 'analise',
    '1053718670': 'analise',
    '1053458456': 'pendente',
    '1053458457': 'assinatura',
    '1053718672': 'concluido',
}

def parse_date(ds):
    if not ds: return None
    try:
        return date.fromisoformat(ds[:10])
    except: return None

def add_bdays(d, n):
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d

def bdays_between(start, end):
    count = 0
    cur = start
    while cur < end:
        if cur.weekday() < 5:
            count += 1
        cur += timedelta(days=1)
    return count

def week_bounds(d):
    mon = d - timedelta(days=d.weekday())
    fri = mon + timedelta(days=4)
    return mon, fri

def extract_company(subj):
    if not subj: return ''
    parts = subj.split('|')
    if len(parts) >= 3:
        return parts[-1].strip()[:30]
    dash = subj.split(' - ')
    if len(dash) >= 2 and '[' not in dash[0] and '{' not in dash[0]:
        return dash[0].strip()[:30]
    for part in reversed(dash):
        p = part.strip()
        if p and '[' not in p and '{' not in p:
            return p[:30]
    return subj[:30]

def extract_tipo(subj):
    s = (subj or '').lower()
    if 'rescis' in s: return 'Rescisão'
    if 'aditivo' in s or 'reajuste' in s or 'renovacao' in s or 'renovação' in s: return 'Aditivo'
    if 'contrato' in s or 'elabora' in s: return 'Contrato'
    return 'Aditivo'

def extract_sol(subj):
    s = subj or ''
    if '[CS]' in s or 'Deal CS' in s: return 'CS'
    if '[Sales]' in s or '{ABM}' in s or 'ABM' in s: return 'Sales'
    return 'CS'

def badge_status(tipo):
    if tipo == 'analise':
        return '<span class="badge b4">&#9679; Em an&#225;lise pelo Legal</span>'
    elif tipo == 'pendente':
        return '<span class="badge b3">&#9203; Ag. CS/Sales ou Empresa</span>'
    elif tipo == 'assinatura':
        return '<span class="badge b2">&#8599; Em assinatura</span>'
    else:
        return '<span class="badge b1">&#10003; Conclu&#237;do</span>'

def tag_tipo(t):
    if t == 'Aditivo': return '<span class="tag tat">Aditivo</span>'
    if t == 'Contrato': return '<span class="tag tsmb">SMB</span>'
    return '<span class="tag tres">Rescis&#227;o</span>'

def tag_sol(s):
    if s == 'CS': return '<span class="tag tcs">CS</span>'
    return '<span class="tag tsl">Sales</span>'

def sla_text(status, created, today):
    if status in ('assinatura','concluido'):
        return 'No prazo', 'sla-ok'
    if status == 'pendente':
        return 'SLA pausado', 'sla-ok'
    # analise
    deadline = add_bdays(created, 3)
    if today <= deadline:
        return f'Vence {deadline.strftime("%d/%b").lower()}', 'sla-ok'
    else:
        late = bdays_between(deadline, today)
        return f'+{late} dia{"s" if late>1 else ""}', 'sla-late'

def format_date(d):
    months = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
    return f'{d.day:02d}/{months[d.month-1]}'

def build_week_html(wid, tickets, today, label, sub):
    if not tickets:
        return ''
    
    counts = {'analise':0,'pendente':0,'assinatura':0,'concluido':0}
    for t in tickets:
        s = STAGES.get(t.get('hs_pipeline_stage',''), 'analise')
        counts[s] = counts.get(s,0) + 1

    rows = ''
    # sort: concluido/assinatura first, then analise, then pendente
    order = {'concluido':0,'assinatura':1,'analise':2,'pendente':3}
    sorted_t = sorted(tickets, key=lambda x: order.get(STAGES.get(x.get('hs_pipeline_stage',''),'pendente'),3))
    
    for t in sorted_t:
        subj = t.get('subject','')
        stage = STAGES.get(t.get('hs_pipeline_stage',''), 'analise')
        emp = extract_company(subj)
        tipo = extract_tipo(subj)
        sol = extract_sol(subj)
        cr = parse_date(t.get('createdate'))
        date_str = format_date(cr) if cr else '—'
        sla, sla_cls = sla_text(stage, cr, today) if cr else ('—','sla-ok')
        subj_esc = htmlmod.escape(subj)
        subj_short = subj_esc[:45] + ('&#8230;' if len(subj)>45 else '')
        emp_esc = htmlmod.escape(emp)
        emp_short = emp_esc[:22] + ('&#8230;' if len(emp)>22 else '')
        rows += f'<tr><td title="{subj_esc}">{subj_short}</td><td title="{emp_esc}">{emp_short}</td><td>{tag_tipo(tipo)}</td><td>{tag_sol(sol)}</td><td>{date_str}</td><td>{badge_status(stage)}</td><td class="{sla_cls}">{sla}</td></tr>\n'

    total = len(tickets)
    return f'''<div id="{wid}" class="sec">
  <div class="cards">
    <div class="card"><div class="card-lbl">Total</div><div class="card-val">{total}</div><div class="card-sub">&nbsp;</div></div>
    <div class="card"><div class="card-lbl">Em an&#225;lise pelo Legal</div><div class="card-val">{counts['analise']}</div></div>
    <div class="card"><div class="card-lbl">Em assinatura</div><div class="card-val">{counts['assinatura']}</div></div>
    <div class="card"><div class="card-lbl">Pend. externas</div><div class="card-val">{counts['pendente']}</div></div>
  </div>
  <div class="panel">
    <table>
      <thead><tr>
        <th style="width:30%">Documento</th><th style="width:18%">Empresa</th><th style="width:9%">Tipo</th>
        <th style="width:7%">Sol.</th><th style="width:8%">Criado</th><th style="width:18%">Status</th><th style="width:10%">SLA</th>
      </tr></thead>
      <tbody>
{rows}      </tbody>
    </table>
  <div class="sla-disclaimer">
    <strong>SLA de 3 dias &#250;teis</strong> &mdash; contagem a partir da cria&#231;&#227;o, apenas dias &#250;teis (seg&#8211;sex). Tickets em <em>Ag. CS/Sales ou Empresa</em> est&#227;o com SLA pausado &#8212; pend&#234;ncia &#233; externa ao Legal.
  </div>
</div>
</div>'''

def build_index(tickets_raw, current_html, today):
    today_d = today
    cur_mon, cur_fri = week_bounds(today_d)
    prev_mon = cur_mon - timedelta(days=7)
    prev_fri = cur_mon - timedelta(days=3)

    # Filter out completed
    active = [t for t in tickets_raw if t.get('hs_pipeline_stage') != '1053718672']

    cur_week = []
    prev_week = []
    for t in active:
        cr = parse_date(t.get('createdate'))
        if not cr: continue
        if cur_mon <= cr <= cur_fri:
            cur_week.append(t)
        elif prev_mon <= cr <= prev_fri:
            prev_week.append(t)

    # Build week label helpers
    def wlabel(mon, fri):
        months = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
        if mon.month == fri.month:
            return f'{mon.day}&#8211;{fri.day}/{months[mon.month-1]}'
        return f'{mon.day}/{months[mon.month-1]}&#8211;{fri.day}/{months[fri.month-1]}'

    # Week IDs
    def week_id(d):
        mon, _ = week_bounds(d)
        return f'w{mon.strftime("%Y%m%d")}'

    wid_cur = week_id(today_d)
    wid_prev = week_id(prev_mon)
    label_cur = wlabel(cur_mon, cur_fri)
    label_prev = wlabel(prev_mon, prev_fri)
    
    def sub_label(mon):
        months = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez']
        # find week number in month
        first = mon.replace(day=1)
        wnum = (mon.day + first.weekday()) // 7 + 1
        return f'{months[mon.month-1]} {wnum}/26'

    sub_cur = sub_label(cur_mon)
    sub_prev = sub_label(prev_mon)

    html_cur = build_week_html(wid_cur, cur_week, today_d, label_cur, sub_cur)
    html_prev = build_week_html(wid_prev, prev_week, today_d, label_prev, sub_prev)

    # Update header date
    today_str = today_d.strftime('%d/%m/%Y')
    result = re.sub(r'Atualizado \d{2}/\d{2}/\d{4} &#224;s \d{2}h\d{2}',
                    f'Atualizado {today_str} &#224;s 09h30', current_html)

    # Remove existing wid_cur and wid_prev sections if present
    for wid in [wid_cur, wid_prev]:
        result = re.sub(rf'<div id="{wid}" class="sec">.*?(?=<div id="|<script>)', '', result, flags=re.DOTALL)

    # Remove tab buttons for these weeks if present (we'll re-add)
    for wid in [wid_cur, wid_prev]:
        result = re.sub(rf'<button[^>]*onclick="sw\(\'{wid}\'[^>]*>.*?</button>\n?', '', result, flags=re.DOTALL)

    # Add new tab buttons after the Visão Geral tab button
    new_tabs = (
        f'<button class="tab on" onclick="sw(\'{wid_cur}\',this)"><span class="tr">{label_cur}</span><span class="ts">{sub_cur}</span></button>\n'
        f'<button class="tab" onclick="sw(\'{wid_prev}\',this)"><span class="tr">{label_prev}</span><span class="ts">{sub_prev}</span></button>\n'
    )
    # Make visão geral tab inactive
    result = result.replace('class="tab on" onclick="sw(\'wg\'', 'class="tab" onclick="sw(\'wg\'')
    # Insert after the visão geral button
    result = re.sub(r'(</button>\n)(<button class="tab")', r'\1' + new_tabs + r'\2', result, count=1)

    # Insert new week sections before the first existing week section
    new_secs = html_cur + '\n' + html_prev + '\n'
    result = re.sub(r'(<div id="w\d{8}" class="sec">|<div id="w0" class="sec">|<div id="wA" class="sec">|<div id="wB" class="sec">)',
                    new_secs + r'\1', result, count=1)

    # Update critical cases
    criticals = sorted(
        [t for t in active if STAGES.get(t.get('hs_pipeline_stage','')) == 'pendente'],
        key=lambda x: parse_date(x.get('createdate')) or date.today()
    )[:2]
    
    critico_html = ''
    for t in criticals:
        cr = parse_date(t.get('createdate'))
        emp = extract_company(t.get('subject',''))
        tipo = extract_tipo(t.get('subject',''))
        days = bdays_between(cr, today_d) if cr else 0
        critico_html += f'''    <div class="critico">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <div class="critico-emp">{htmlmod.escape(emp[:30])}</div>
        <div class="critico-dias">+{days} dias &#250;teis</div>
      </div>
      <div class="critico-det">{htmlmod.escape(t.get("subject","")[:60])}...</div>
      <div style="margin-top:4px">{tag_tipo(tipo)} <span style="font-size:10px;color:#6B4D63">Ag. CS/Sales ou Empresa</span></div>
    </div>\n'''

    # Replace critical section content
    result = re.sub(
        r'(<div class="panel-lbl" style="color:#993C1D">Casos cr&#237;ticos</div>).*?(?=\s*</div>\s*</div>\s*<div class="panel">)',
        r'\1\n' + critico_html,
        result, flags=re.DOTALL
    )

    # Update last-updated counter in overview
    total_tickets = len([t for t in tickets_raw])
    
    return result

if __name__ == '__main__':
    tickets_file = sys.argv[1]
    html_file = sys.argv[2]
    
    with open(tickets_file) as f:
        raw = json.load(f)
    
    # Handle both array and HubSpot wrapped response
    if isinstance(raw, list):
        tickets = raw
    elif 'results' in raw:
        tickets = raw['results']
        tickets = [t.get('properties', t) for t in tickets]
    else:
        tickets = []
    
    with open(html_file) as f:
        current_html = f.read()
    
    today = date.today()
    updated = build_index(tickets, current_html, today)
    
    with open(html_file, 'w') as f:
        f.write(updated)
    
    print(f"Done: {len(tickets)} tickets processed, {today}")
