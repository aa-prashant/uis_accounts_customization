import re
import json
import urllib.parse
import urllib.request
import ssl
import frappe

def _follow_redirects(url: str) -> str:
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            return resp.geturl()
    except Exception:
        return url

def _extract_candidates(u: str):
    # 1) Prefer !3d<lat>!4d<lng>
    c1 = re.search(r"!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)", u)
    if c1:
        return float(c1.group(1)), float(c1.group(2))

    # 2) Fallback: @<lat>,<lng>
    c2 = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", u)
    if c2:
        return float(c2.group(1)), float(c2.group(2))

    # 3) Fallbacks in the querystring: q=, ll=, query=
    parsed = urllib.parse.urlparse(u)
    q = urllib.parse.parse_qs(parsed.query)
    for key in ["q", "ll", "query"]:
        vals = q.get(key, [])
        for val in vals:
            m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$", val)
            if m:
                return float(m.group(1)), float(m.group(2))

    return None, None

def _valid(lat, lng):
    return lat is not None and lng is not None and -90 <= lat <= 90 and -180 <= lng <= 180

@frappe.whitelist()
def extract_lat_lng_from_maps_url(url: str) -> str:
    if not url:
        return json.dumps({"ok": False, "message": "Empty URL"})

    final_url = _follow_redirects(url)
    lat, lng = _extract_candidates(final_url)

    # last chance: try original if redirect didn’t expose coords
    if not _valid(lat, lng):
        lat, lng = _extract_candidates(url)

    if not _valid(lat, lng):
        return json.dumps({"ok": False, "message": "Could not find coordinates in the provided link."})

    # Return as-is (client already converts to GeoJSON and handles swap if needed)
    return json.dumps({"ok": True, "lat": lat, "lng": lng})

def set_address_lines(doc, method):
    if doc.custom_national_address_arabic:
        lines = (doc.custom_national_address_arabic or "").splitlines()

        first_line = ""
        if len(lines) > 0:
            first_line = lines[0].strip()
        doc.address_line1 = first_line[:240]

        second_line = ""
        if len(lines) > 1:
            second_line = lines[1].strip()
        doc.address_line2 = second_line[:240]