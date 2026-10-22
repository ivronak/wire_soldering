# Demo tour ki ગુજરાતી awaaz banata hai: scripts/tour_narration.py ke har step ka mp3 -> app/static/audio/gu/<step-id>.mp3
# Chalane ke liye internet chahiye (Microsoft neural Gujarati voice, edge-tts).  Sirf badli / nayi lines dobara banti hain.
#   venv/Scripts/python.exe scripts/build_tour_audio.py            (default voice: Dhwani, mahila)
#   venv/Scripts/python.exe scripts/build_tour_audio.py --force    (sab dobara)
import asyncio
import hashlib
import json
import os
import sys

import edge_tts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from tour_narration import NARRATION  # noqa: E402

VOICE = "gu-IN-DhwaniNeural"
RATE = "-4%"
OUT = os.path.join(ROOT, "app", "static", "audio", "gu")
MANIFEST = os.path.join(OUT, "manifest.json")


def tour_step_ids():
    # tour.js ke saare step ids (taaki koi step bina awaaz ke na rahe)
    import re
    src = open(os.path.join(ROOT, "app", "static", "js", "tour.js"), encoding="utf-8").read()
    return re.findall(r"\{ id: '([\w-]+)', type: '\w+'", src)


async def make(step_id, text):
    path = os.path.join(OUT, step_id + ".mp3")
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, VOICE, rate=RATE).save(path)
            return os.path.getsize(path)
        except Exception as error:      # network / service ka hiccup
            print("  retry", step_id, attempt + 1, error)
            await asyncio.sleep(2 * (attempt + 1))
    raise SystemExit(f"Could not create audio for {step_id}")


async def main():
    force = "--force" in sys.argv
    os.makedirs(OUT, exist_ok=True)
    ids = tour_step_ids()
    missing = [i for i in ids if i not in NARRATION]
    extra = [i for i in NARRATION if i not in ids]
    if missing or extra:
        raise SystemExit(f"Narration mismatch. Missing: {missing}  Unknown: {extra}")
    manifest = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
    built = 0
    for step_id in ids:
        text = NARRATION[step_id]
        digest = hashlib.sha1((VOICE + RATE + text).encode("utf-8")).hexdigest()[:12]
        if not force and manifest.get(step_id, {}).get("hash") == digest and os.path.exists(os.path.join(OUT, step_id + ".mp3")):
            continue
        size = await make(step_id, text)
        manifest[step_id] = {"hash": digest, "bytes": size, "chars": len(text)}
        built += 1
        print(f"  {step_id:16s} {size // 1024:4d} KB")
    manifest = {k: v for k, v in manifest.items() if k in ids}
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(v["bytes"] for v in manifest.values())
    print(f"Done. {built} new, {len(manifest)} total, {total // 1024} KB, voice {VOICE}")


asyncio.run(main())
