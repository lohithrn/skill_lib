#!/usr/bin/env python3
"""OOXML shape-builder atoms for branded content slides.

Emit DrawingML shape XML strings to append into a duplicated content
slide's <p:spTree> (before </p:spTree>). Coordinates in INCHES; converted
to EMU internally. Keeps the native title/subtitle placeholders and the
inherited content-layout footer untouched.

Colors: pass 6-hex WITHOUT '#'.

The palette below is a PLACEHOLDER. Overwrite these constants with the values
you extracted from your own template (see references/template_spec.md) before
you build; every pattern reads them from here, so one edit re-brands the set.
"""
import re

EMU = 914400
def IN(v): return int(round(v * EMU))

# Placeholder palette — swap for your template's real values.
ACCENT = "2B6CB0"; ACCENT_ALT = "3182CE"
DARK = "1B2233"; INK = "1A1E28"; SLATE = "5A6172"
LIGHT = "F4F5F7"; BORDER = "E4E6EB"
RED = "841018"; GREEN = "2E7D5B"; MAGENTA = "C92C8F"; AMBER = "E8A33D"
WHITE = "FFFFFF"

HEAD = "Cambria"   # safe serif for stat numbers / accents
BODY = "Calibri"   # safe sans body

_id = [1000]
def _nid():
    _id[0] += 1
    return _id[0]

def _solid(c): return f'<a:solidFill><a:srgbClr val="{c}"/></a:solidFill>'

def _shadow():
    return ('<a:effectLst><a:outerShdw blurRad="90000" dist="30000" '
            'dir="5400000" rotWithShape="0"><a:srgbClr val="8A8F9C">'
            '<a:alpha val="26000"/></a:srgbClr></a:outerShdw></a:effectLst>')

def _xfrm(x, y, w, h):
    return (f'<a:off x="{IN(x)}" y="{IN(y)}"/>'
            f'<a:ext cx="{IN(w)}" cy="{IN(h)}"/>')

def rrect(x, y, w, h, fill, line=BORDER, lw=9525, radius=0.09, shadow=True):
    frac = min(0.5, radius / min(w, h)) if min(w, h) > 0 else 0
    adj = f'<a:avLst><a:gd name="adj" fmla="val {int(frac*100000)}"/></a:avLst>'
    ln = (f'<a:ln w="{lw}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
          if line else '<a:ln><a:noFill/></a:ln>')
    eff = _shadow() if shadow else ''
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{_nid()}" name="rr"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>{_xfrm(x,y,w,h)}</a:xfrm>'
            f'<a:prstGeom prst="roundRect">{adj}</a:prstGeom>{_solid(fill)}{ln}{eff}'
            f'</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p>'
            f'<a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>')

def rect(x, y, w, h, fill, line=None, lw=9525):
    ln = (f'<a:ln w="{lw}"><a:solidFill><a:srgbClr val="{line}"/></a:solidFill></a:ln>'
          if line else '<a:ln><a:noFill/></a:ln>')
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{_nid()}" name="r"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>{_xfrm(x,y,w,h)}</a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>{_solid(fill)}{ln}'
            f'</p:spPr><p:txBody><a:bodyPr/><a:lstStyle/><a:p>'
            f'<a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>')

def ellipse(x, y, w, h, fill, shadow=True):
    eff = ('<a:effectLst><a:outerShdw blurRad="60000" dist="20000" dir="5400000" '
           'rotWithShape="0"><a:srgbClr val="000000"><a:alpha val="18000"/>'
           '</a:srgbClr></a:outerShdw></a:effectLst>') if shadow else ''
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{_nid()}" name="e"/><p:cNvSpPr/>'
            f'<p:nvPr/></p:nvSpPr><p:spPr><a:xfrm>{_xfrm(x,y,w,h)}</a:xfrm>'
            f'<a:prstGeom prst="ellipse"><a:avLst/></a:prstGeom>{_solid(fill)}'
            f'<a:ln><a:noFill/></a:ln>{eff}</p:spPr><p:txBody><a:bodyPr/>'
            f'<a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>')

def _esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _runs(runs):
    out = ''
    for text, o in runs:
        rpr = f'<a:rPr lang="en-US" sz="{o.get("sz",1300)}"'
        if o.get('b'): rpr += ' b="1"'
        if o.get('i'): rpr += ' i="1"'
        if o.get('spc'): rpr += f' spc="{o["spc"]}"'
        rpr += ' dirty="0">' + _solid(o.get('c', INK))
        if o.get('face'): rpr += f'<a:latin typeface="{o["face"]}"/>'
        rpr += '</a:rPr>'
        pres = ' xml:space="preserve"' if text != text.strip() else ''
        out += f'<a:r>{rpr}<a:t{pres}>{_esc(text)}</a:t></a:r>'
    return out

def txt(x, y, w, h, paras, align='l', anchor='t', mL=0, mR=0, mT=0, mB=0):
    """paras: list of (runs, opts). runs: list of (text, run_opts).
       para opts: bullet(bool), spcAft(pts*100), lnPct(e.g.105000), align override."""
    anc = {'t': 't', 'm': 'ctr', 'b': 'b'}[anchor]
    body = (f'<a:bodyPr wrap="square" lIns="{mL}" tIns="{mT}" rIns="{mR}" '
            f'bIns="{mB}" anchor="{anc}"><a:normAutofit/></a:bodyPr>')
    ps = ''
    for runs, po in paras:
        pPr = f'<a:pPr algn="{po.get("align", align)}">'
        if po.get('lnPct'):
            pPr = pPr[:-1] + f'><a:lnSpc><a:spcPct val="{po["lnPct"]}"/></a:lnSpc>'
        if po.get('spcAft') is not None:
            pPr += f'<a:spcAft><a:spcPts val="{po["spcAft"]}"/></a:spcAft>'
        pPr += ('<a:buFont typeface="Arial"/><a:buChar char="&#8226;"/>'
                if po.get('bullet') else '<a:buNone/>')
        pPr += '</a:pPr>'
        ps += f'<a:p>{pPr}{_runs(runs)}</a:p>'
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{_nid()}" name="t"/><p:cNvSpPr>'
            f'<a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr/></p:nvSpPr><p:spPr>'
            f'<a:xfrm>{_xfrm(x,y,w,h)}</a:xfrm><a:prstGeom prst="rect"><a:avLst/>'
            f'</a:prstGeom><a:noFill/></p:spPr><p:txBody>{body}<a:lstStyle/>{ps}</p:txBody></p:sp>')

def pic(rid, x, y, w, h):
    """rid = relationship id (e.g. 'rId5') of an embedded image in the slide's .rels."""
    return (f'<p:pic><p:nvPicPr><p:cNvPr id="{_nid()}" name="p"/><p:cNvPicPr>'
            f'<a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
            f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/>'
            f'</a:stretch></p:blipFill><p:spPr><a:xfrm>{_xfrm(x,y,w,h)}</a:xfrm>'
            f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>')

def icon_chip(x, y, d, rid, fill=ACCENT):
    """Accent (or semantic) circle + white icon PNG (rid) inset ~46%."""
    ip = d * 0.46
    return (ellipse(x, y, d, d, fill)
            + pic(rid, x + (d - ip) / 2, y + (d - ip) / 2, ip, ip))

# ---- insertion + bounds-check utilities -------------------------------

def inject(slide_xml, shapes):
    """Insert a list of shape XML strings before </p:spTree>."""
    body = ''.join(shapes)
    return slide_xml.replace('</p:spTree>', body + '</p:spTree>', 1)

def swap_title(slide_xml, new_text):
    """Replace the text of the title placeholder, keeping its formatting."""
    return re.sub(r'(<p:ph type="title".*?<a:t>)(.*?)(</a:t>)',
                  lambda m: m.group(1) + _esc(new_text) + m.group(3),
                  slide_xml, count=1, flags=re.S)

def check_bounds(slide_xml, cx=12192000, cy=6858000, slack=5000):
    """Return list of out-of-bounds (x0,y0,x1,y1) in inches for QA."""
    bad = []
    for m in re.finditer(r'<a:off x="(-?\d+)" y="(-?\d+)"/><a:ext cx="(\d+)" cy="(\d+)"/>', slide_xml):
        ox, oy, w, h = map(int, m.groups())
        if ox < 0 or oy < 0 or ox + w > cx + slack or oy + h > cy + slack:
            bad.append(tuple(round(v/914400, 2) for v in (ox, oy, ox+w, oy+h)))
    return bad
