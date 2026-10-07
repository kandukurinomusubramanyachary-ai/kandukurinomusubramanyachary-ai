#!/usr/bin/env python3
"""Generate self-contained SVGs for the GitHub profile README.

Uses only the Python standard library and GitHub's GraphQL API. Generated SVGs
are committed back to the profile repository by GitHub Actions.
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

API = "https://api.github.com/graphql"
OUT = Path(__file__).resolve().parents[1] / "assets"
WIDTH = 760
ACCENT = "#A78BFA"
MONO = "ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,'Liberation Mono','Courier New',monospace"
RAMP = ["·", ":", "+", "#", "@"]

PROFILE = {
    "name": "Subramanya Chary",
    "handle": "kandukurinomusubramanyachary-ai",
    "role": "FOUNDER · AI ENGINEER · PRODUCT BUILDER",
    "tagline": "I build systems, not demos.",
    "focus": "AI systems · product engineering · applied research",
}

# Hide old iterations/duplicates from the public narrative while keeping the
# underlying repositories untouched.
EXCLUDE_REPOS = {
    "bloom3", "bloom.app", "BLOOM.", "wholebloom",
    "MEDLENS.", "medlens-final", "MEDLENSFINAL.",
}
DESCRIPTIONS = {
    "BLOOMv3": "AI-native wellbeing companion for cycle, symptoms and daily support",
    "EARTHPULSE": "Satellite imagery → time-series change detection → evidence",
    "Medlens": "Structured patient intake and report tooling",
}

QUERY = r"""
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(
      first: 100,
      ownerAffiliations: OWNER,
      isFork: false,
      privacy: PUBLIC,
      orderBy: {field: PUSHED_AT, direction: DESC}
    ) {
      totalCount
      nodes {
        name url description pushedAt diskUsage isArchived stargazerCount
        primaryLanguage { name }
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

def utc_window():
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return f"{start.isoformat()}T00:00:00Z", f"{today.isoformat()}T23:59:59Z"

def fetch(login: str, token: str):
    start, end = utc_window()
    payload = json.dumps({"query": QUERY, "variables": {"login": login, "from": start, "to": end}}).encode()
    req = urllib.request.Request(
        API, data=payload,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-self-generating-profile",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = json.load(response)
    if body.get("errors"):
        raise SystemExit(f"GitHub GraphQL error: {body['errors']}")
    user = (body.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"GitHub user not found: {login}")
    return user

def theme_css(extra=""):
    return f"""
    .fg{{fill:#24292f}} .muted{{fill:#656d76}} .rule{{stroke:#d0d7de}}
    .accent{{fill:{ACCENT}}} .accent-stroke{{stroke:{ACCENT}}}
    .soft{{fill:#f6f8fa}} .panel{{fill:#ffffff;stroke:#d0d7de}}
    text{{font-family:{MONO}}}
    @media (prefers-color-scheme: dark) {{
      .fg{{fill:#f0f6fc}} .muted{{fill:#8b949e}} .rule{{stroke:#30363d}}
      .soft{{fill:#161b22}} .panel{{fill:#0d1117;stroke:#30363d}}
    }}
    {extra}
    """

def svg_open(width, height, extra_css=""):
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f"<style>{theme_css(extra_css)}</style>",
    ]

def txt(x, y, value, size=13, cls="fg", weight=400, anchor="start", opacity=None, letter=None):
    attrs = [f'x="{x}"', f'y="{y}"', f'class="{cls}"', f'font-size="{size}"', f'font-weight="{weight}"']
    if anchor != "start": attrs.append(f'text-anchor="{anchor}"')
    if opacity is not None: attrs.append(f'opacity="{opacity}"')
    if letter is not None: attrs.append(f'letter-spacing="{letter}"')
    return f"<text {' '.join(attrs)}>{escape(str(value))}</text>"

def clip_reveal(cid, x, y, width, height, begin, dur=0.9):
    clip = (
        f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="0" height="{height}">'
        f'<animate attributeName="width" from="0" to="{width}" begin="{begin}s" dur="{dur}s" fill="freeze"/>'
        f"</rect></clipPath>"
    )
    cursor = (
        f'<rect y="{y}" width="2" height="{height}" class="accent" opacity="0">'
        f'<animate attributeName="x" from="{x}" to="{x + width}" begin="{begin}s" dur="{dur}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.9" begin="{begin}s"/>'
        f'<set attributeName="opacity" to="0" begin="{begin + dur}s"/>'
        f"</rect>"
    )
    return clip, cursor

def normalize(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    days = [d for week in weeks for d in week]
    weekly = [sum(d["contributionCount"] for d in week) for week in weeks]

    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    current, current_start, current_end = 0, None, None
    for d in reversed(tail):
        if d["contributionCount"] == 0:
            break
        current += 1
        current_start = d["date"]
        current_end = current_end or d["date"]

    longest, best_start, best_end = 0, None, None
    run, run_start = 0, None
    for d in days:
        if d["contributionCount"] > 0:
            run += 1
            run_start = run_start or d["date"]
            if run > longest:
                longest, best_start, best_end = run, run_start, d["date"]
        else:
            run, run_start = 0, None

    repos = [
        r for r in (user["repositories"]["nodes"] or [])
        if r.get("name") not in EXCLUDE_REPOS
    ]
    language_bytes = {}
    for repo in repos:
        for edge in (repo.get("languages") or {}).get("edges") or []:
            lang = edge["node"]["name"]
            language_bytes[lang] = language_bytes.get(lang, 0) + edge["size"]
    languages = sorted(language_bytes.items(), key=lambda kv: (-kv[1], kv[0]))[:6]
    recent = [
        r for r in repos
        if not r.get("isArchived")
        and (r.get("diskUsage") or 0) > 0
        and r.get("name") != PROFILE["handle"]
    ][:5]
    return {
        "total": cal["totalContributions"],
        "active_days": sum(1 for d in days if d["contributionCount"] > 0),
        "best_week": max(weekly) if weekly else 0,
        "weekly": weekly, "weeks": weeks,
        "current": current, "current_start": current_start, "current_end": current_end,
        "longest": longest, "longest_start": best_start, "longest_end": best_end,
        "repo_count": user["repositories"]["totalCount"],
        "languages": languages, "recent": recent,
    }

def short_date(iso):
    if not iso: return "—"
    d = date.fromisoformat(iso[:10])
    return d.strftime("%b %d").lower().replace(" 0", " ")

def draw_identity(s):
    recent = s.get("recent") or []
    current = recent[0]["name"] if recent else "Bloom"
    p = svg_open(WIDTH, 282)
    p.append('<rect x="0.5" y="0.5" width="759" height="281" rx="18" class="panel"/>')
    p.append(txt(28,38,"subbu@github:~$ ./whoami",12,"muted",600))
    clip,cursor=clip_reveal("idname",28,58,470,54,.12,1.05)
    p += [clip, f'<g clip-path="url(#idname)">{txt(28,100,PROFILE["name"].upper(),32,"fg",700,letter="1.1")}</g>', cursor]
    p.append(txt(28,130,PROFILE["role"],12,"muted",600,letter="1.0"))
    p.append(txt(28,165,PROFILE["tagline"],17,"fg",600))
    p.append(txt(28,190,PROFILE["focus"],12,"muted"))
    p.append('<line x1="28" y1="216" x2="732" y2="216" class="rule" stroke-width="1"/>')
    p.append(txt(28,244,"CURRENT",10,"muted",700,letter="1.2"))
    p.append(txt(100,244,current,13,"fg",600))
    p.append(txt(28,266,"STATUS",10,"muted",700,letter="1.2"))
    p.append('<circle cx="104" cy="262" r="4" class="accent"><animate attributeName="opacity" values="1;.25;1" dur="1.8s" repeatCount="indefinite"/></circle>')
    p.append(txt(116,266,"shipping",13,"fg",600))
    art=["  @@@@@@      @@@@@@  "," @@          @@       "," @@           @@      ","  @@@@@        @@@@@   ","      @@           @@  ","      @@          @@   "," @@@@@@      @@@@@@    "]
    for i,line in enumerate(art):
        cid=f"mono{i}"; clip,cur=clip_reveal(cid,525,50+i*19,190,18,.18+i*.07,.45)
        p += [clip, f'<g clip-path="url(#{cid})">{txt(525,64+i*19,line,13,"accent",700)}</g>', cur]
    p.append(txt(525,218,"SELF-GENERATING PROFILE",9,"muted",700,letter="1.1"))
    p.append(txt(525,238,"github actions · graphql · svg",10,"muted"))
    p.append("</svg>")
    return "".join(p)

def draw_stats(s):
    p=svg_open(WIDTH,180)
    p.append(txt(0,54,s["total"],48,"fg",700))
    p.append(txt(0,77,"contributions · last 365 days",11,"muted"))
    for i,(value,label) in enumerate([(s["active_days"],"active days"),(s["best_week"],"best week"),(s["repo_count"],"public repos")]):
        x=430+i*110
        p.append(txt(x,42,value,21,"fg",700,"middle")); p.append(txt(x,64,label,9,"muted",600,"middle"))
    weekly=s.get("weekly") or [0]; peak=max(weekly) or 1; base,top=164,104; step=WIDTH/max(len(weekly)-1,1)
    pts=[(i*step,base-(v/peak)*(base-top)) for i,v in enumerate(weekly)]
    path="M"+" L".join(f"{x:.1f},{y:.1f}" for x,y in pts)
    area=f"M{pts[0][0]:.1f},{base} "+" ".join(f"L{x:.1f},{y:.1f}" for x,y in pts)+f" L{pts[-1][0]:.1f},{base} Z"
    p.append(f'<path d="{area}" class="accent" opacity=".08"/>')
    clip,cursor=clip_reveal("statline",0,top-4,WIDTH,base-top+8,.25,1.2)
    p += [clip, f'<path d="{path}" class="accent-stroke" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" clip-path="url(#statline)"/>', cursor, "</svg>"]
    return "".join(p)

def draw_streak(s):
    p=svg_open(WIDTH,108); p.append('<line x1="380" y1="14" x2="380" y2="94" class="rule" stroke-width="1"/>')
    cells=[(s["current"],"current streak",s.get("current_start"),s.get("current_end")),(s["longest"],"longest streak",s.get("longest_start"),s.get("longest_end"))]
    for i,(n,label,start,end) in enumerate(cells):
        x=40 if i==0 else 420
        p += [txt(x,50,f"{n} days",28,"fg",700),txt(x,72,label,10,"muted",700,letter=".8"),txt(x,91,f"{short_date(start)} → {short_date(end)}" if n else "—",10,"muted")]
    p.append("</svg>"); return "".join(p)

def draw_langs(s):
    p=svg_open(WIDTH,178); langs=s.get("languages") or []; total=sum(v for _,v in langs) or 1
    if not langs: p.append(txt(0,44,"No public language data yet.",13,"muted"))
    for i,(name,value) in enumerate(langs):
        y=18+i*25; frac=value/total
        p += [txt(0,y+10,name.lower(),11,"fg",600),f'<rect x="125" y="{y}" width="{540*frac:.1f}" height="8" rx="4" class="accent" opacity="{max(.22,.75-i*.08):.2f}"/>',txt(750,y+9,f"{frac*100:.0f}%",10,"muted",600,"end")]
    p.append("</svg>"); return "".join(p)

def draw_year(s):
    weeks=s.get("weeks") or []; p=svg_open(WIDTH,146)
    p += [txt(0,18,"THE LAST YEAR",10,"muted",700,letter="1.2"),txt(0,39,f'{s["active_days"]} active days · one character per day',11,"fg")]
    max_day=max((d["contributionCount"] for w in weeks for d in w),default=1) or 1
    for wi,week in enumerate(weeks):
        for d in week:
            c=d["contributionCount"]; idx=0 if c<=0 else min(4,max(1,math.ceil((c/max_day)*4)))
            x=24+wi*6.6; y=58+d["weekday"]*11.2
            p.append(txt(f"{x:.1f}",f"{y:.1f}",RAMP[idx],8.7,"accent" if idx>=3 else "muted",700,opacity=.95 if idx else .35))
    p += [txt(0,140,"less  · : + # @  more",9,"muted"),"</svg>"]; return "".join(p)

def draw_activity(s):
    repos=s.get("recent") or []; p=svg_open(WIDTH,40+max(1,len(repos[:4]))*54)
    p.append(txt(0,17,"RECENT PUBLIC WORK",10,"muted",700,letter="1.2"))
    for i,repo in enumerate(repos[:4]):
        y=42+i*54; lang=((repo.get("primaryLanguage") or {}).get("name") or "—").lower(); pushed=short_date(repo.get("pushedAt"))
        desc=(DESCRIPTIONS.get(repo["name"]) or repo.get("description") or "working repository").strip().replace("\n"," ")
        if len(desc)>68: desc=desc[:65].rstrip()+"..."
        p += [txt(0,y,repo["name"],13,"fg",700),txt(750,y,f"{lang} · {pushed}",10,"muted",600,"end"),txt(0,y+20,desc,10,"muted")]
        if i != min(3,len(repos)-1): p.append(f'<line x1="0" y1="{y+33}" x2="760" y2="{y+33}" class="rule" stroke-width="1" opacity=".65"/>')
    p.append("</svg>"); return "".join(p)

def draw_heading(label):
    p=svg_open(WIDTH,30); p.append(txt(0,20,label.lower(),15,"fg",700)); start=min(180,len(label)*10+24)
    p += [f'<line x1="{start}" y1="14" x2="760" y2="14" class="rule" stroke-width="1"/>',"</svg>"]; return "".join(p)

def write(name,content):
    OUT.mkdir(parents=True,exist_ok=True); path=OUT/name
    old=path.read_text(encoding="utf-8") if path.exists() else None
    if old==content: return False
    path.write_text(content,encoding="utf-8"); return True

def main():
    token=os.environ.get("GITHUB_TOKEN"); login=os.environ.get("GH_LOGIN",PROFILE["handle"])
    if not token: raise SystemExit("GITHUB_TOKEN is required")
    s=normalize(fetch(login,token))
    outputs={
        "identity.svg":draw_identity(s),"stats.svg":draw_stats(s),"streak.svg":draw_streak(s),
        "langs.svg":draw_langs(s),"year.svg":draw_year(s),"activity.svg":draw_activity(s),
        "hd-building.svg":draw_heading("building now"),"hd-projects.svg":draw_heading("selected engineering"),
        "hd-stats.svg":draw_heading("system telemetry"),"hd-stack.svg":draw_heading("stack"),
        "hd-about.svg":draw_heading("about this profile"),
    }
    changed=[name for name,content in outputs.items() if write(name,content)]
    print("updated:" if changed else "no changes:",", ".join(changed) if changed else "none")

if __name__=="__main__":
    main()
